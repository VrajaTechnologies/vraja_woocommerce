from odoo import models, fields


class WooCommercePaymentGateway(models.Model):
    _name = 'woocommerce.payment.gateway'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Payment Gateway'

    name = fields.Char(string='Name', help='Enter Name', copy=False, tracking=True)
    code = fields.Char(string='Code', help='Enter Code', copy=False, tracking=True)
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', help='Select company', copy=False, tracking=True)

    def import_woocommerce_payment_gateway(self, instance):
        """
        This method import payment gateway through Order API.
        """
        try:
            log_id = self.env['woocommerce.log'].generate_woocommerce_logs('gateway', 'import', instance,
                                                                           'Process Started')
            url = "{0}/wp-json/wc/v3/payment_gateways".format(instance.woocommerce_url)
            response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("GET", url)
            if response_status:
                for payment_gateway_response in response_data:
                    self.search_or_create_woocommerce_payment_gateway(instance, payment_gateway_response, log_id)
                log_id.woocommerce_operation_message = 'Process Has Been Finished'
            else:
                message = "Getting Some Error When Try To Import Gateway"
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('gateway', 'import', instance,
                                                                                   message, False, response_data,
                                                                                   log_id, True)
        except Exception as error:
            message = "Getting Some Error When Try To Import Gateway"
            self.env['woocommerce.log.line'].generate_woocommerce_process_line('gateway', 'import', instance, message,
                                                                               False, error, log_id, True)

    def search_or_create_woocommerce_payment_gateway(self, instance, payment_gateway_response=False, log_id=False,
                                                     code=False, name=False):
        """
        This method searches for payment gateway and create it, if not found.
        """
        gateway_id = payment_gateway_response.get('id') if payment_gateway_response else code
        gateway_name = payment_gateway_response.get('method_title') if payment_gateway_response else name
        payment_gateway_id = self.search([('code', '=', gateway_id), ('instance_id', '=', instance.id)], limit=1)
        if not payment_gateway_id:
            payment_gateway_id = self.create({'name': gateway_name, 'code': gateway_id, 'instance_id': instance.id,
                                              'company_id': instance.company_id.id})
            self.env['woocommerce.financial.status.configuration'].create_woocommerce_financial_status(instance, 'paid')
            self.env['woocommerce.financial.status.configuration'].create_woocommerce_financial_status(instance,
                                                                                                       'not_paid')
            msg = "Gateway Successfully Created {}".format(gateway_name)

        else:
            msg = "Gateway Already exist {}".format(gateway_name)
        self.env['woocommerce.log.line'].generate_woocommerce_process_line('gateway', 'import', instance, msg, False,
                                                                           payment_gateway_response, log_id, False)
        return payment_gateway_id
