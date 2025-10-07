import logging
import pprint
from odoo import models, api, fields, tools, _
from datetime import timedelta

_logger = logging.getLogger("Customer Queue Line")


class CustomerDataQueue(models.Model):
    _name = 'woocommerce.customer.data.queue'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'WooCommerce Customer Data'

    @api.depends('customer_queue_line_ids.state')
    def _compute_customer_queue_line_state_and_count(self):
        for queue in self:
            queue_line_ids = queue.customer_queue_line_ids
            if all(line.state == 'draft' for line in queue_line_ids):
                queue.state = 'draft'
            elif all(line.state == 'failed' for line in queue_line_ids):
                queue.state = 'failed'
            elif all(line.state == 'completed' for line in queue_line_ids):
                queue.state = 'completed'
            else:
                queue.state = 'partially_completed'

    name = fields.Char(size=120, readonly=True, )
    instance_id = fields.Many2one("woocommerce.instance.integration", string="Instance")
    state = fields.Selection([("draft", "Draft"), ("partially_completed", "Partially Completed"),
                              ("completed", "Completed"), ("failed", "Failed")],
                             default="draft", store=True, compute="_compute_customer_queue_line_state_and_count")
    customer_queue_line_ids = fields.One2many("woocommerce.customer.data.queue.line",
                                              "customer_queue_id", "Customers")
    queue_process_count = fields.Integer(help="It is used for know, how many time queue is processed.")
    woocommerce_log_id = fields.Many2one('woocommerce.log', string="Logs")

    @api.model
    def create(self, vals):
        sequence = self.env.ref("vraja_woocommerce_odoo_integration.seq_woocommerce_customer_queue")
        name = sequence and sequence.next_by_id() or '/'
        if type(vals) == dict:
            vals.update({'name': name})
        return super(CustomerDataQueue, self).create(vals)

    def generate_woocommerce_customer_queue(self, instance):
        queue_id = self.create({
            'instance_id': instance.id,
        })
        return queue_id

    def create_woocommerce_customer_queue_job(self, instance_id, woocommerce_customer_list):
        """This method used to create a customer queue """
        res_id_list = []
        batch_size = 50
        for woocommerce_customer in tools.split_every(batch_size, woocommerce_customer_list):
            queue_id = self.generate_woocommerce_customer_queue(instance_id)
            for customer in woocommerce_customer:
                woocommerce_customer_dict = customer
                self.env['woocommerce.customer.data.queue.line'].create_woocommerce_customer_queue_line(
                    woocommerce_customer_dict,
                    instance_id, queue_id)
            res_id_list.append(queue_id.id)
        return res_id_list

    def fetch_customers_from_woocommerce_to_odoo(self, instance, from_date, to_date,customer_id=''):
        """This method used to fetch a woocommerce customer"""
        woocommerce_customer_list = []
        try:
            url = "{0}/wp-json/wc/v3/customers/{1}".format(instance.woocommerce_url,customer_id)
            response_status, response_data,next_page_link = instance.woocommerce_api_calling_process("GET", url)
            if not response_status:
                _logger.info("Getting Some error while fetch customer from woocommerce : {0}".format(response_data))
                return False
            woocommerce_customer_list = response_data
            _logger.info(woocommerce_customer_list)
        except Exception as error:
            _logger.info("Getting Some Error In Fetch The customer :: {0}".format(error))
        return woocommerce_customer_list

    def import_customers_from_woocommerce_to_odoo(self, instance, from_date=False, to_date=False):
        """
        This method use for import customer shopipy to odoo
        """
        # instance.test_woocommerce_connection()
        from_date = fields.Datetime.now() - timedelta(10) if not from_date else from_date
        to_date = fields.Datetime.now() if not to_date else to_date
        woocommerce_customer_list = self.fetch_customers_from_woocommerce_to_odoo(instance, from_date, to_date)
        if woocommerce_customer_list:
            res_id_list = self.create_woocommerce_customer_queue_job(instance, woocommerce_customer_list)
            # instance.last_synced_customer_date = to_date
            return res_id_list

    def process_woocommerce_customer_queue(self):
        """
        This method is used for Create Customer from woocommerce To Odoo
        From customer queue create customer in odoo
        """

        instance_id = self.instance_id
        log_id = self.env['woocommerce.log'].generate_woocommerce_logs('customer', 'import', instance_id,
                                                                       'Process Started')
        for rec in self.customer_queue_line_ids:
            try:
                customer_data = eval(rec.customer_data_to_process)
                customer_id, msg, fault, line_state = self.env[
                    'res.partner'].create_update_customer_woocommerce_to_odoo(log_id,instance_id,
                                                                              customer_data=customer_data)
                if customer_id:
                    rec.res_partner_id = customer_id.id
                    rec.state = line_state
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('customer', 'import',
                                                                                       instance_id,
                                                                                       msg,
                                                                                       False, customer_data, log_id,
                                                                                       False)
                    self._cr.commit()
                else:
                    rec.state = line_state
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('customer', 'import',
                                                                                       instance_id,
                                                                                       msg,
                                                                                       False, msg, log_id, True)
            except Exception as error:
                _logger.info(error)
        self.woocommerce_log_id = log_id.id
        log_id.woocommerce_operation_message = 'Process Has Been Finished'


class CustomerDataQueueLine(models.Model):
    _name = 'woocommerce.customer.data.queue.line'
    _description = 'Customer Data Line'

    name = fields.Char(string='Customer')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id',
                                  copy=False)
    customer_id = fields.Char(string="Customer ID", help='This is the Customer Id of woocommerce customer',
                              copy=False)
    state = fields.Selection([('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
                              ('completed', 'Completed'), ('failed', 'Failed')], tracking=True,
                             default='draft', copy=False)
    customer_data_to_process = fields.Text(string="customer Data", copy=False)
    customer_queue_id = fields.Many2one('woocommerce.customer.data.queue', string='Customer Queue')
    res_partner_id = fields.Many2one("res.partner")

    #
    def create_woocommerce_customer_queue_line(self, woocommerce_customer_dict, instance_id, queue_id):
        """This method used to create a woocommerce customer queue  line """

        name = "%s %s" % (
            woocommerce_customer_dict.get('first_name') or "", (woocommerce_customer_dict.get('last_name') or ""))
        customer_queue_line_id = self.create({
            'customer_id': woocommerce_customer_dict.get('id'),
            'state': 'draft',
            'name': name.strip(),
            'customer_data_to_process': pprint.pformat(woocommerce_customer_dict),
            'instance_id': instance_id and instance_id.id or False,
            'customer_queue_id': queue_id and queue_id.id or False,
        })
        return customer_queue_line_id
