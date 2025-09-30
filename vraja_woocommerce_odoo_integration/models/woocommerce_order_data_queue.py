# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, tools, _
from datetime import datetime, timedelta
from odoo.tools.safe_eval import safe_eval
import logging
import pprint
import pytz

_logger = logging.getLogger("WooCommerce Order Queue")


class WooCommerceOrderDataQueue(models.Model):
    _name = "woocommerce.order.data.queue"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "WooCommerce Order Data Queue"
    _order = 'id DESC'

    @api.depends('woocommerce_order_queue_line_ids.state')
    def _compute_queue_line_state_and_count(self):
        for queue in self:
            queue_line_ids = queue.woocommerce_order_queue_line_ids
            if all(line.state == 'draft' for line in queue_line_ids):
                queue.state = 'draft'
            elif all(line.state == 'failed' for line in queue_line_ids):
                queue.state = 'failed'
            elif all(line.state == 'completed' for line in queue_line_ids):
                queue.state = 'completed'
            else:
                queue.state = 'partially_completed'

    name = fields.Char(string='Name')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id',
                                  copy=False, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
                              ('completed', 'Completed'), ('failed', 'Failed')], tracking=True,
                             default='draft', compute="_compute_queue_line_state_and_count", store=True)

    woocommerce_order_queue_line_ids = fields.One2many("woocommerce.order.data.queue.line",
                                                       "woocommerce_order_queue_id", string="Order Queue")
    woocommerce_log_id = fields.Many2one('woocommerce.log', string="Logs")

    @api.model
    def create(self, vals):
        sequence = self.env.ref("vraja_woocommerce_odoo_integration.seq_woocommerce_order_queue")
        name = sequence and sequence.next_by_id() or '/'
        if type(vals) == dict:
            vals.update({'name': name})
        return super(WooCommerceOrderDataQueue, self).create(vals)

    def unlink(self):
        """
        This method is used for unlink queue lines when deleting main queue
        """
        for queue in self:
            if queue.woocommerce_order_queue_line_ids:
                queue.woocommerce_order_queue_line_ids.unlink()
        return super(WooCommerceOrderDataQueue, self).unlink()

    def create_woocommerce_order_queue_job(self, instance, woocommerce_order_list):
        res_id_list = []
        batch_size = 50
        for woocommerce_orders in tools.split_every(batch_size, woocommerce_order_list):
            queue_id = self.create({'instance_id': instance.id})
            for woocommerce_order in woocommerce_orders:
                woocommerce_order_dict = woocommerce_order
                self.env['woocommerce.order.data.queue.line'].create_woocommerce_order_queue_line(
                    woocommerce_order_dict, 'draft',
                    instance, queue_id)
            res_id_list.append(queue_id.id)
        return res_id_list

    def fetch_orders_from_woocommerce_to_odoo(self, instance, from_date, to_date, woocommerce_order_ids):
        """This method used to fetch a woocommerce orders"""
        woocommerce_order_list = []
        from_date = pytz.utc.localize(from_date).astimezone(pytz.timezone(instance.woocommerce_store_timezone))
        to_date = pytz.utc.localize(to_date).astimezone(pytz.timezone(instance.woocommerce_store_timezone))
        try:
            params = {'include': woocommerce_order_ids} if woocommerce_order_ids else {"after": from_date,
                                                                                       "before": to_date,
                                                                                       }
            url = "{0}/wp-json/wc/v3/orders".format(instance.woocommerce_url)
            response_status, response_data = instance.woocommerce_api_calling_process("GET", url, params=params)
            if not response_status:
                _logger.info("Getting Some error while fetch customer from Woocommerce : {0}".format(response_data))
                return False
            woocommerce_order_list = response_data
            _logger.info(woocommerce_order_list)
        except Exception as error:
            _logger.info("Getting Some Error In Fetch The customer :: {0}".format(error))
        return woocommerce_order_list

    def import_order_from_woocommerce_to_odoo(self, instance, from_date=False, to_date=False,
                                              woocommerce_order_ids=False):
        from_date = from_date if from_date else fields.Datetime.now() - timedelta(10)
        to_date = to_date if to_date else fields.Datetime.now()

        woocommerce_order_list = self.fetch_orders_from_woocommerce_to_odoo(instance, from_date, to_date,
                                                                            woocommerce_order_ids)
        if woocommerce_order_list:
            res_id_list = self.create_woocommerce_order_queue_job(instance, woocommerce_order_list)
            # instance.woocommerce_last_synced_order_date = to_date
            return res_id_list

    def process_woocommerce_order_queue(self, instance_id=False):
        """This method was used for process the order queue line from order queue"""

        sale_order_object, instance_id = self.env['sale.order'], instance_id if instance_id else self.instance_id

        order_data_queues = self
        for order_data_queue in order_data_queues:
            if order_data_queue.woocommerce_log_id:
                log_id = order_data_queue.woocommerce_log_id
            else:
                log_id = self.env['woocommerce.log'].generate_woocommerce_logs('order', 'import', instance_id,
                                                                               'Process Started')
            self._cr.commit()
            order_data_queue_lines = order_data_queue.woocommerce_order_queue_line_ids.filtered(
                lambda x: x.state in ['draft', 'partially_completed', 'failed'])
            for line in order_data_queue_lines:
                try:
                    woocommerce_order_dictionary = safe_eval(line.order_data_to_process)
                    result, msg,fault_or_not,line_state = sale_order_object.process_import_order_from_woocommerce(
                        woocommerce_order_dictionary,
                        instance_id, log_id, line)
                    if result:
                        line.state = line_state
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line('order', 'import',
                                                                                           instance_id,
                                                                                           msg,
                                                                                           False,
                                                                                           woocommerce_order_dictionary,
                                                                                           log_id,
                                                                                           fault_or_not)
                    else:
                        line.state = line_state
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line('order', 'import',
                                                                                           instance_id, msg,
                                                                                           False, msg, log_id,
                                                                                           fault_or_not)
                except Exception as error:
                    _logger.info(error)
            self.woocommerce_log_id = log_id.id
            log_id.woocommerce_operation_message = 'Process Has Been Finished'
            if not log_id.woocommerce_operation_line_ids:
                log_id.unlink()


class WoocommerceOrderDataQueueLine(models.Model):
    _name = 'woocommerce.order.data.queue.line'
    _description = "Woocommerce Order Data Queue Line"
    _rec_name = 'woocommerce_order_queue_id'

    name = fields.Char(string='Name')
    woocommerce_order_queue_id = fields.Many2one('woocommerce.order.data.queue', string='Order Data Queue')

    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id')
    order_data_id = fields.Char(string="Order Data ID", help='This is the Order Id of Woocommerce Order')
    state = fields.Selection(
        [('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
         ('completed', 'Completed'), ('failed', 'Failed')], tracking=True,
        default='draft')
    order_data_to_process = fields.Text(string="Order Data")
    # number_of_fails = fields.Integer(string="Number of attempts",
    #                                  help="This field gives information regarding how many time we will try to proceed the order",
    #                                  copy=False)
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")

    def create_woocommerce_order_queue_line(self, woocommerce_order_dict, state, instance_id,
                                            queue_id):
        order_queue_line_id = self.create({
            'order_data_id': woocommerce_order_dict.get('id'),
            'state': state,
            # 'name': shopify_order_dict.strip(),
            'order_data_to_process': pprint.pformat(woocommerce_order_dict),
            'instance_id': instance_id.id,
            'woocommerce_order_queue_id': queue_id.id
        })
        return order_queue_line_id
