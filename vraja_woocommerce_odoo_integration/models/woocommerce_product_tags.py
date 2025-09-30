from odoo import models, fields


class ProductCategory(models.Model):
    _name = "woocommerce.product.tags"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Product tags'

    name = fields.Char(string='Name', help='Enter Name', copy=False, tracking=True)
    code = fields.Char(string='Code', help='Enter Code', copy=False, tracking=True)
    slug = fields.Char(string='Slug', help='Enter Slug', copy=False, tracking=True)
    sequence = fields.Integer(required=1)
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', help='Select company', copy=False, tracking=True)

    def import_product_tags(self, instance):
        """
        This method import product tags through Order API.
        """
        try:
            log_id = self.env['woocommerce.log'].generate_woocommerce_logs('product_tags', 'import', instance,
                                                                           'Process Started')
            url = "{0}/wp-json/wc/v3/products/tags".format(instance.woocommerce_url)
            response_status, response_data = instance.woocommerce_api_calling_process("GET", url)
            if response_status:
                for product_tags_response in response_data:
                    self.search_or_create_product_tags(instance, product_tags_response, log_id)
                log_id.woocommerce_operation_message = 'Process Has Been Finished'
            else:
                message = "Getting Some Error When Try To Import product tags"
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product_tags', 'import', instance,
                                                                                   message, False, response_data,
                                                                                   log_id, True)
        except Exception as error:
            message = "Getting Some Error When Try To Import product tags"
            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product_tags', 'import', instance,
                                                                               message,
                                                                               False, error, log_id, True)

    def search_or_create_product_tags(self, instance, product_tags_response, log_id):
        """
        This method searches for product tags and create it, if not found.
        """
        tags_id = product_tags_response.get('id')
        tags_name = product_tags_response.get('name')
        slug = product_tags_response.get('slug')
        product_category_id = self.search([('code', '=', tags_id), ('instance_id', '=', instance.id)], limit=1)
        if not product_category_id:
            self.create({'name': tags_name, 'code': tags_id, 'instance_id': instance.id,
                         'company_id': instance.company_id.id, 'slug': slug})
            msg = "product category Successfully Created {}".format(tags_name)
        else:
            msg = "product Already exist {}".format(tags_name)
        self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'import', instance, msg, False,
                                                                           product_tags_response, log_id, False)
