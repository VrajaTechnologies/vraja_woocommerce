from odoo import models, fields, api
import pprint


class ProcessDetail(models.Model):
    _name = 'woocommerce.log'
    _inherit = ['mail.thread']
    _order = 'id DESC'


    name = fields.Char(string='Name')
    woocommerce_operation_name = fields.Selection([('gateway', 'Gateway'),
                                                   ('shipping', 'Shipping'),
                                                   ('product', 'Product'),
                                                   ('customer', 'Customer'),
                                                   ('location', 'location'),
                                                   ('product_attribute', 'Product Attribute'),
                                                   ('product_variant', 'Product Variant'),
                                                   ('product_category', 'Product Category'),
                                                   ('product_tags', 'Product tags'),
                                                   ('order', 'Order'), ('inventory', 'Inventory')],
                                                  string="Process Name")
    woocommerce_operation_type = fields.Selection([('export', 'Export'),
                                                   ('import', 'Import'),
                                                   ('update', 'Update'),
                                                   ('delete', 'Cancel / Delete')], string="Process Type")
    company_id = fields.Many2one('res.company', string='Company')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id',
                                  copy=False, tracking=True)
    woocommerce_operation_line_ids = fields.One2many("woocommerce.log.line", "woocommerce_operation_id",
                                                     string="Operation")
    woocommerce_operation_message = fields.Char(string="Message")
    create_date = fields.Datetime(string='Created on')

    @api.model
    def create(self, vals):
        sequence = self.env.ref("vraja_woocommerce_odoo_integration.seq_woocommerce_log")
        name = sequence and sequence.next_by_id() or '/'
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        if type(vals) == dict:
            vals.update({'name': name, 'company_id': company_id})
        return super(ProcessDetail, self).create(vals)

    def unlink(self):
        "This method is used for unlink appropriate log and logline both from both log model"
        for selected_main_log in self:
            # log_lines = self.env['woocommerce.log.line'].search([('woocommerce_operation_id','=',selected_main_log.id)])
            if selected_main_log.woocommerce_operation_line_ids:
                selected_main_log.woocommerce_operation_line_ids.unlink()
        return super(ProcessDetail, self).unlink()

    def generate_woocommerce_logs(self, woocommerce_operation_name, woocommerce_operation_type, instance,
                                  woocommerce_operation_message):
        log_id = self.create({
            'woocommerce_operation_name': woocommerce_operation_name,
            'woocommerce_operation_type': woocommerce_operation_type,
            'instance_id': instance.id,
            'woocommerce_operation_message': woocommerce_operation_message
        })
        return log_id


class ProcessDetailsLine(models.Model):
    _name = 'woocommerce.log.line'
    _rec_name = 'woocommerce_operation_id'

    woocommerce_operation_id = fields.Many2one('woocommerce.log', string='Process')
    woocommerce_operation_name = fields.Selection([('gateway', 'Gateway'),
                                                   ('shipping', 'Shipping'),
                                                   ('product', 'Product'),
                                                   ('location', 'location'),
                                                   ('customer', 'Customer'),
                                                   ('product_attribute', 'Product Attribute'),
                                                   ('product_variant', 'Product Variant'),
                                                   ('product_category', 'Product Category'),
                                                   ('product_tags', 'Product tags'),
                                                   ('order', 'Order'), ('inventory', 'Inventory')],
                                                  string="Process Name")

    woocommerce_operation_type = fields.Selection([('export', 'Export'),
                                                   ('import', 'Import'),
                                                   ('update', 'Update'),
                                                   ('delete', 'Cancel / Delete')], string="Process Type")
    company_id = fields.Many2one("res.company", "Company")
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id',
                                  copy=False, tracking=True)
    process_request_message = fields.Char("Request Message", copy=False)
    process_response_message = fields.Text("Response Message", copy=False)
    fault_operation = fields.Boolean("Fault Process", default=False)
    woocommerce_operation_message = fields.Char("Message")
    create_date = fields.Datetime(string='Created on')
    product_queue_line = fields.Many2one('woocommerce.product.data.queue.line')

    @api.model
    def create(self, vals):
        if type(vals) == dict:
            woocommerce_operation_id = vals.get('woocommerce_operation_id')
            operation = woocommerce_operation_id and self.env['woocommerce.log'].browse(
                woocommerce_operation_id) or False
            company_id = operation and operation.company_id.id or self.env.user.company_id.id
            vals.update({'company_id': company_id})
        return super(ProcessDetailsLine, self).create(vals)

    def generate_woocommerce_process_line(self, woocommerce_operation_name, woocommerce_operation_type, instance,
                                          woocommerce_operation_message, process_request_message,
                                          process_response_message,
                                          log_id, fault_operation=False):
        log_line_id = self.create({
            'woocommerce_operation_name': woocommerce_operation_name,
            'woocommerce_operation_type': woocommerce_operation_type,
            'instance_id': instance.id,
            'woocommerce_operation_message': woocommerce_operation_message,
            'process_request_message': pprint.pformat(process_request_message) if process_request_message else False,
            'process_response_message': pprint.pformat(process_response_message) if process_response_message else False,
            'woocommerce_operation_id': log_id and log_id.id,
            'fault_operation': fault_operation
        })
        return log_line_id
