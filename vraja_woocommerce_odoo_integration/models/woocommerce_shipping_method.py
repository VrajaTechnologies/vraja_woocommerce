from odoo import models, fields, _

class WooCommerceShippingMethod(models.Model):
    _name = "woocommerce.shipping.method"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "WooCommerce Shipping Method"

    name = fields.Char("Shipping Method", required=True)
    code = fields.Char("Shipping Code", required=True,
                       help="The shipping code should match Shipping ID in your WooCommerce Checkout Settings.")
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', help='Select company', copy=False, tracking=True)

    def import_shipping_method(self, instance):
        """
        This method import shipping method through Order API.
        """
        try:
            log_id = self.env['woocommerce.log'].generate_woocommerce_logs('shipping', 'import', instance,
                                                                           'Process Started')
            url = "{0}/wp-json/wc/v3/shipping_methods".format(instance.woocommerce_url)
            response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("GET", url)
            if response_status:
                for shipping_method_response in response_data:
                    self.search_or_create_shipping_method(instance, shipping_method_response, log_id)
                log_id.woocommerce_operation_message = 'Process Has Been Finished'
            else:
                message = "Getting Some Error When Try To Import shipping Method"
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('shipping', 'import', instance,
                                                                                   message, False, response_data,
                                                                                   log_id, True)
        except Exception as error:
            message = "Getting Some Error When Try To Import shipping Method"
            self.env['woocommerce.log.line'].generate_woocommerce_process_line('shipping', 'import', instance, message,
                                                                               False, error, log_id, True)

    def search_or_create_shipping_method(self, instance, shipping_method_response, log_id):
        """
        This method searches for shipping method and create it, if not found.
        """
        shipping_id = shipping_method_response.get('id')
        shipping_name = shipping_method_response.get('title')
        shipping_method_id = self.search([('code', '=', shipping_id), ('instance_id', '=', instance.id)], limit=1)
        if not shipping_method_id:
            self.create({'name': shipping_name, 'code': shipping_id, 'instance_id': instance.id,
                         'company_id': instance.company_id.id})
            msg = "Shipping Method Successfully Created {}".format(shipping_name)
        else:
            msg = "Shipping Method Already exist {}".format(shipping_name)
        self.env['woocommerce.log.line'].generate_woocommerce_process_line('shipping', 'import', instance, msg, False,
                                                                           shipping_method_response, log_id, False)
