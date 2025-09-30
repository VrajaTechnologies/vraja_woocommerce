from odoo import models, fields
from datetime import timedelta


class WooCommerceOperations(models.TransientModel):
    _name = 'woocommerce.operations'
    _description = 'woocommerce Import Export'

    def _get_default_marketplace(self):
        instance_id = self._context.get('active_id')
        return instance_id

    # def _get_default_from_date_order(self):
    #     instance_id = self.env.context.get('active_id')
    #     instance_id = self.env['woocommerce.instance.integration'].search([('id', '=', instance_id)], limit=1)
    #     from_date_order = instance_id.last_order_synced_date if instance_id.last_order_synced_date else fields.Datetime.now() - timedelta(
    #         30)
    #     from_date_order = fields.Datetime.to_string(from_date_order)
    #     return from_date_order
    # #
    def _get_default_to_date(self):
        to_date = fields.Datetime.now()
        to_date = fields.Datetime.to_string(to_date)
        return to_date

    def _get_default_from_date_product(self):
        instance_id = self.env.context.get('active_id')
        instance_id = self.env['woocommerce.instance.integration'].search([('id', '=', instance_id)], limit=1)
        from_date = instance_id.woocommerce_last_product_synced_date if instance_id.woocommerce_last_product_synced_date else fields.Datetime.now() - timedelta(
            30)
        from_date = fields.Datetime.to_string(from_date)
        return from_date

    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance',
                                  default=_get_default_marketplace)
    woocommerce_operation = fields.Selection([('import', 'Import'), ('export', 'Export')],
                                             string='WooCommerce Operations', default='import')
    import_operations = fields.Selection([('import_order', 'Import Order'),
                                          ("import_product", "Import Product"),
                                          ("import_customers", "Import Customer"),
                                          ("import_stock", "Import Stock"),
                                          ("import_payment_gateways", "Import Payment Gateways"),
                                          ("import_shipping_method", "Import Shipping Method"),
                                          ("import_product_category", "Import Product Category"),
                                          ("import_product_tags", "Import Product Tags")],
                                         string='Import Operations', default='import_order')

    from_date_order = fields.Datetime(string='From Date')
    to_date_order = fields.Datetime(string='To Date')
    woocommerce_order_id = fields.Char(string='Order IDs')

    #
    # Import Product fields
    from_date_product = fields.Datetime(string='From Date', default=_get_default_from_date_product)
    to_date_product = fields.Datetime(string='To Date', default=_get_default_to_date)
    woocommerce_product_ids = fields.Char(string='Product IDs')

    # Import Stock
    # auto_validate_inventory_in_odoo = fields.Boolean(default=False, string='Auto Validate Inventory in Odoo?',
    #                                                  help="If you select it, the inventory in odoo will be validate automatically.")

    def execute_process_of_woocommerce(self):
        instance = self.instance_id
        queue_ids = False
        if self.import_operations == "import_payment_gateways":
            self.env["woocommerce.payment.gateway"].import_woocommerce_payment_gateway(instance)
        if self.import_operations == "import_shipping_method":
            self.env['woocommerce.shipping.method'].import_shipping_method(instance)
        if self.import_operations == "import_order":
            self.env["woocommerce.order.data.queue"].import_order_from_woocommerce_to_odoo(instance,
                                                                                           self.from_date_order,
                                                                                           self.to_date_order,
                                                                                           self.woocommerce_order_id)
        if self.import_operations == "import_customers":
            self.env['woocommerce.customer.data.queue'].import_customers_from_woocommerce_to_odoo(instance)
        if self.import_operations == "import_product_category":
            self.env['woocommerce.product.category'].import_product_category(instance)
        if self.import_operations == "import_product_tags":
            self.env['woocommerce.product.tags'].import_product_tags(instance)
        if self.import_operations == "import_product":
            product_queue_ids = self.env['woocommerce.product.data.queue'].import_product_from_woocommerce_to_odoo(instance,
                                                                                                       self.from_date_product,
                                                                                                       self.to_date_product,
                                                                                                       self.woocommerce_product_ids)
            if product_queue_ids:
                queue_ids = product_queue_ids
                model_action = "vraja_woocommerce_odoo_integration.action_woocommerce_product_process"
                model_form = "vraja_woocommerce_odoo_integration.view_woocommerce_product_queue_form"

        # if self.import_operations == "import_order":
        #     order_queue_ids = self.env['sale.order'].import_orders_from_woocommerce_to_odoo(instance,
        #                                                                                     self.from_date_order,
        #                                                                                     self.to_date_order,
        #                                                                                     self.woocommerce_order_id)
        #     if order_queue_ids:
        #         queue_ids = order_queue_ids
        #         model_action = "vraja_woocommerce_odoo_integration.action_woocommerce_order_process"
        #         model_form = "vraja_woocommerce_odoo_integration.view_form_woocommerce_order_queue_form"
        #

        #
        #
        # if self.import_operations == "import_customers":
        #     from_date = instance.last_synced_customer_date
        #     to_date = fields.Datetime.now()
        #     if not from_date:
        #         from_date = fields.Datetime.now() - timedelta(10)
        #     action = self.env['customer.data.queue'].import_customers_from_woocommerce_to_odoo(instance, from_date,
        #                                                                                        to_date)
        #
        # if self.import_operations == "import_stock":
        #     woocommerce_product_listing_item = self.env['woocommerce.product.listing.item']
        #     inventory_records = woocommerce_product_listing_item.import_stock_from_woocommerce_to_odoo(instance,
        #                                                                                                self.auto_validate_inventory_in_odoo)
        #
        # # Based on queue ids, action & form view open particular model with created queue records.
        # if queue_ids and model_action and model_form:
        #     action = self.env.ref(model_action).sudo().read()[0]
        #     form_view = self.sudo().env.ref(model_form)
        #
        #     if len(queue_ids) != 1:
        #         action["domain"] = [("id", "in", queue_ids)]
        #     else:
        #         action.update({"view_id": (form_view.id, form_view.name), "res_id": queue_ids[0],
        #                        "views": [(form_view.id, "form")]})
        #     return action
