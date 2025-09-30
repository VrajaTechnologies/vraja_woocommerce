import logging
import re
import requests

from datetime import timedelta
from odoo import models, fields, tools, api
import pprint

_logger = logging.getLogger("WooCommerce Product Queue")


class WooCommerceProductDataQueue(models.Model):
    _name = "woocommerce.product.data.queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "WooCommerece Product Data Queue"
    _order = 'id DESC'

    @api.depends('woocommerce_product_queue_line_ids.state')
    def _compute_product_queue_line_state_and_count(self):
        for queue in self:
            queue_line_ids = queue.woocommerce_product_queue_line_ids
            if all(line.state == 'draft' for line in queue_line_ids):
                queue.state = 'draft'
            elif all(line.state == 'failed' for line in queue_line_ids):
                queue.state = 'failed'
            elif all(line.state == 'completed' for line in queue_line_ids):
                queue.state = 'completed'
            else:
                queue.state = 'partially_completed'

    name = fields.Char(string='Name')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id')
    state = fields.Selection(selection=[('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
                                        ('completed', 'Completed'), ('failed', 'Failed')],
                             tracking=True, default='draft', compute="_compute_product_queue_line_state_and_count")
    product_queue_line_total_record = fields.Integer(string='Total Records',
                                                     help="This Button Shows Number of Total Records")
    product_queue_line_draft_record = fields.Integer(string='Draft Records',
                                                     help="This Button Shows Number of Draft Records")
    product_queue_line_fail_record = fields.Integer(string='Fail Records',
                                                    help="This Button Shows Number of Fail Records")
    product_queue_line_done_record = fields.Integer(string='Done Records',
                                                    help="This Button Shows Number of Done Records")
    product_queue_line_cancel_record = fields.Integer(string='Cancel Records',
                                                      help="This Button Shows Number of Done Records")
    woocommerce_product_queue_line_ids = fields.One2many("woocommerce.product.data.queue.line",
                                                     "woocommerce_product_queue_id", "Product Queue Lines")
    woocommerce_log_id = fields.Many2one('woocommerce.log', string="Logs")

    @api.model_create_multi
    def create(self, vals_list):
        """
        This method is used to add sequence number in new record.
        """
        sequence = self.env.ref("vraja_woocommerce_odoo_integration.woocommerce_seq_product_queue")
        for vals in vals_list:
            name = sequence and sequence.next_by_id() or '/'
            if type(vals) == dict:
                vals.update({'name': name})
        return super(WooCommerceProductDataQueue, self).create(vals_list)

    def unlink(self):
        """
        This method is used for unlink queue lines when deleting main queue
        """
        for queue in self:
            if queue.woocommerce_product_queue_line_ids:
                queue.woocommerce_product_queue_line_ids.unlink()
        return super(WooCommerceProductDataQueue, self).unlink()

    def generate_woocommerce_product_queue(self, instance):
        return self.create({'instance_id': instance.id})

    def create_woocommerce_product_queue_job(self, instance_id, woocommerce_product_list):
        """
        Based on the batch size product queue will create.
        """
        queue_id_list = []
        batch_size = 50
        for woocommerce_products in tools.split_every(batch_size, woocommerce_product_list):
            queue_id = self.generate_woocommerce_product_queue(instance_id)
            for product in woocommerce_products:
                woocommerce_product_dict = product
                self.env['woocommerce.product.data.queue.line'].create_woocommerce_product_queue_line(woocommerce_product_dict, instance_id,
                                                                                      queue_id)
            queue_id_list.append(queue_id.id)
        return queue_id_list

    def fetch_product_from_woocommerce_to_odoo(self,instance, from_date=False, to_date=False, woocommerce_product_ids=''):
        """
        From WooCommerce library API calls to get product response.
        """
        woocommerce_product_list = []
        params = {"per_page": 100}  # Always define params

        try:
            if woocommerce_product_ids:
                # Extract only numeric IDs from the string
                template_ids = list(set(re.findall(r"(\d+)", woocommerce_product_ids)))
                if template_ids:
                    params["include"] = ",".join(template_ids)
                    _logger.info("Fetching products by IDs: %s", params["include"])

                url = "{0}/wp-json/wc/v3/products/".format(instance.woocommerce_url)
                response_status, response_data,next_page_link = instance.woocommerce_api_calling_process("GET", url, params=params)

                if not response_status:
                    _logger.error("Error while fetching products by ID from WooCommerce: %s", response_data)
                    return False

                woocommerce_product_list = response_data
                _logger.info("Fetched %s products from WooCommerce by IDs", len(woocommerce_product_list))
                return woocommerce_product_list
            else:
                if from_date:
                    params["after"] = from_date.isoformat() if hasattr(from_date, "isoformat") else from_date
                if to_date:
                    params["before"] = to_date.isoformat() if hasattr(to_date, "isoformat") else to_date

                url = "{0}/wp-json/wc/v3/products/".format(instance.woocommerce_url)
                response_status, response_data,next_page_link = instance.woocommerce_api_calling_process("GET", url, params=params)

                if not response_status:
                    _logger.error("Error while fetching products by date from WooCommerce: %s", response_data)
                    return False

                woocommerce_product_list = response_data
                _logger.info("Fetched %s products from WooCommerce by date range", len(woocommerce_product_list))

        except Exception as error:
            _logger.exception("Exception while fetching products from WooCommerce: %s", error)

        return woocommerce_product_list

    def import_product_from_woocommerce_to_odoo(self, instance, from_date=False, to_date=False, woocommerce_product_ids=False):
        """
        From operation wizard's button this method will call if product import option get selected.
        """
        queue_id_list, woocommerce_product_list = [], []
        from_date = fields.Datetime.now() - timedelta(10) if not from_date else from_date
        to_date = fields.Datetime.now() if not to_date else to_date
        last_synced_date = fields.Datetime.now()

        if woocommerce_product_ids:
            woocommerce_product_list = self.fetch_product_from_woocommerce_to_odoo(instance,woocommerce_product_ids=woocommerce_product_ids)
        else:
            woocommerce_product_list = self.fetch_product_from_woocommerce_to_odoo(instance,from_date=from_date, to_date=to_date)
        if woocommerce_product_list:
            queue_id_list = self.create_woocommerce_product_queue_job(instance, woocommerce_product_list)
            if queue_id_list:
                instance.woocommerce_last_product_synced_date = last_synced_date
        return queue_id_list

    def process_woocommerce_product_queue(self, instance_id=False):
        """
        In product queue given process button, from this button this method get executed.
        From this method from Woocommerce product will get imported into Odoo.
        """
        woocommerce_product_object, instance_id = self.env['woocommerce.product.listing'], instance_id or self.instance_id

        if self._context.get('from_cron'):
            product_data_queues = self.search([('instance_id', '=', instance_id.id), ('state', '!=', 'completed')],
                                              order="id asc")
        else:
            product_data_queues = self
        for product_data_queue in product_data_queues:
            if product_data_queue.woocommerce_log_id:
                log_id = product_data_queue.woocommerce_log_id
            else:
                log_id = self.env['woocommerce.log'].generate_woocommerce_logs('product', 'import', instance_id,
                                                                       'Process Started')
            self._cr.commit()

            if self._context.get('from_cron'):
                product_data_queue_lines = product_data_queue.woocommerce_product_queue_line_ids.filtered(
                    lambda x: x.state in ['draft', 'partially_completed'])
            else:
                product_data_queue_lines = product_data_queue.woocommerce_product_queue_line_ids.filtered(
                    lambda x: x.state in ['draft', 'partially_completed', 'failed'] and x.number_of_fails < 3)

            commit_counter = 0
            for line in product_data_queue_lines:
                commit_counter += 1
                if commit_counter == 10:
                    self._cr.commit()
                    commit_counter = 0
                try:
                    product_id = woocommerce_product_object.woocommerce_create_products(product_queue_line=line,
                                                                                instance=instance_id,
                                                                                log_id=log_id)
                    if not product_id:
                        line.number_of_fails += 1
                except Exception as error:
                    line.state = 'failed'
                    error_msg = 'Getting Some Error When Try To Process Product Queue From Woocommerce To Odoo'
                    self.env['woocommerce.log.line'].with_context(for_variant_line=line).generate_woocommerce_process_line('product', 'import', instance_id,
                                                                               error_msg,
                                                                               False, error, log_id, True)
                    _logger.info(error)
            self.woocommerce_log_id = log_id.id
            log_id.woocommerce_operation_message = 'Process Has Been Finished'
            if not log_id.woocommerce_operation_line_ids:
                log_id.unlink()

    def process_woocommerce_product_queue_using_cron(self):
        """This method was used for process Product data queue automatically using cron job"""
        instance_ids = self.env['woocommerce.instance.integration'].search([])
        if instance_ids:
            for instance_id in instance_ids:
                self.with_context(from_cron=True).process_woocommerce_product_queue(instance_id)


class WoocommerceProductDataQueueLine(models.Model):
    _name = "woocommerce.product.data.queue.line"
    _description = "Product Data Queue Line"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string='Name')
    woocommerce_product_queue_id = fields.Many2one('woocommerce.product.data.queue', string='Product Data Queue')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance',
                                  help='Select Instance Id')
    product_data_id = fields.Char(string="Product Data ID", help='This is the Product Id of Woocommerce Product')
    state = fields.Selection(selection=[('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
                                        ('completed', 'Completed'), ('failed', 'Failed')], default='draft')
    product_data_to_process = fields.Text(string="Product Data")
    number_of_fails = fields.Integer(string="Number of attempts",
                                     help="This field gives information regarding how many time we will try to proceed the order",
                                     copy=False)
    log_line = fields.One2many('woocommerce.log.line', 'product_queue_line')

    def create_woocommerce_product_queue_line(self, woocommerce_product_dict, instance_id, queue_id):
        """
        From this method queue line will create.
        """
        product_queue_line_id = self.create({
            'product_data_id': woocommerce_product_dict.get('id'),
            'state': 'draft',
            'name': woocommerce_product_dict.get('name', '').strip(),
            'product_data_to_process': pprint.pformat(woocommerce_product_dict),
            'instance_id': instance_id and instance_id.id or False,
            'woocommerce_product_queue_id': queue_id and queue_id.id or False,
        })
        return product_queue_line_id
