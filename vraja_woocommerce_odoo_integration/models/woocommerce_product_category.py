from odoo import models, fields


class ProductCategory(models.Model):
    _name = "woocommerce.product.category"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Product Category'

    name = fields.Char(string='Name', help='Enter Name', copy=False, tracking=True)
    code = fields.Char(string='Code', help='Enter Code', copy=False, tracking=True)
    slug = fields.Char(string='Slug', help='Enter Slug', copy=False, tracking=True)
    # parent_id = fields.Char(string='Parent Id', help='Enter Parent Id', copy=False, tracking=True)
    parent_id = fields.Many2one('woocommerce.product.category', string='Parent', index=True, ondelete='cascade')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', help='Select company', copy=False, tracking=True)

    def import_product_category(self, instance):
        """
        This method import product category through Order API.
        """
        try:
            log_id = self.env['woocommerce.log'].generate_woocommerce_logs('product_category', 'import', instance,
                                                                           'Process Started')
            url = "{0}/wp-json/wc/v3/products/categories".format(instance.woocommerce_url)
            response_status, response_data,next_page_link = instance.woocommerce_api_calling_process("GET", url)
            if response_status:
                for product_category_response in response_data:
                    self.search_or_create_product_category(instance, product_category_response, log_id)
                log_id.woocommerce_operation_message = 'Process Has Been Finished'
            else:
                message = "Getting Some Error When Try To Import product category"
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'import', instance,
                                                                                   message, False, response_data,
                                                                                   log_id, True)
        except Exception as error:
            message = "Getting Some Error When Try To Import product category"
            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product_category', 'import', instance,
                                                                               message,
                                                                               False, error, log_id, True)

    def search_or_create_product_category(self, instance, product_category_response, log_id):
        """
        This method searches for product category and create it, if not found.
        """
        category_id = product_category_response.get('id')
        category_name = product_category_response.get('name')
        slug = product_category_response.get('slug')
        parent_id = product_category_response.get('parent')
        product_category_id = self.search([('code', '=', category_id), ('instance_id', '=', instance.id)], limit=1)
        if not product_category_id:
            self.create({'name': category_name, 'code': category_id, 'instance_id': instance.id,
                         'company_id': instance.company_id.id, 'slug': slug, 'parent_id': parent_id})
            msg = "product category Successfully Created {}".format(category_name)
        else:
            msg = "product Already exist {}".format(category_name)
        self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'import', instance, msg, False,
                                                                           product_category_response, log_id, False)
