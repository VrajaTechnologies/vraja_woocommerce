import logging
import requests
import base64
import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.addons.base.models.res_partner import _tz_get

_logger = logging.getLogger("WooCommerce")


class WooCommerceInstanceIntegrations(models.Model):
    _name = 'woocommerce.instance.integration'
    _description = 'WooCommerce Instance Integration'

    @api.model
    def woocommerce_tz_get(self):
        return _tz_get(self)

    name = fields.Char(string='Name', help='Enter Instance Name', copy=False, tracking=True)
    active = fields.Boolean(string='Active', copy=False, tracking=True, default=True)
    company_id = fields.Many2one('res.company', string='Company', help='Select Company', copy=False, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', help='Select Warehouse', copy=False,
                                   tracking=True)
    woocommerce_url = fields.Char(string='API Url', help='Enter WooCommerce Url', copy=False, tracking=True)
    woocommerce_key = fields.Char(string='Consumer Key', help='Enter WooCommerce API Key', copy=False, tracking=True)
    woocommerce_secret = fields.Char(string='Consumer Secret ', help='Enter WooCommerce Secret Key', copy=False,
                                     tracking=True)
    woocommerce_store_timezone = fields.Selection("woocommerce_tz_get", help="Timezone of Woocommerce Store")

    woocommerce_last_synced_order_date = fields.Datetime(string="Last Sync Order Date", copy=False)
    woocommerce_last_product_synced_date = fields.Datetime(string="Last Sync Order Date", copy=False)
    woocommerce_shipping_product_id = fields.Many2one('product.product', string="Woocommerce Shipping Product",
                                                      copy=False, tracking=True,
                                                      default=lambda self: self.env.ref(
                                                          'vraja_woocommerce_odoo_integration.shipping_product', False),
                                                      help="this product will be considered as a Shipping product for add \n"
                                                           "sale order line")
    woocommerce_fee_product_id = fields.Many2one('product.product', string="Woocommerce Fee Product",
                                                 copy=False, tracking=True,
                                                 default=lambda self: self.env.ref(
                                                     'vraja_woocommerce_odoo_integration.fee_product', False),
                                                 help="This product will be considered as a fee product for add \n"
                                                      "sale order line")
    image = fields.Binary(string="Image", help="Select Image.")
    woocommerce_price_list_id = fields.Many2one('product.pricelist', string="Price List", copy=False, tracking=True)
    woocommerce_apply_tax_in_order = fields.Selection(
        [("odoo_tax", "Odoo Default Tax Behaviour"), ("create_woocommerce_tax",
                                                      "Create WooCommerce Tax")], default='odoo_tax',
        copy=False, help=""" For Woocommerce Orders :- \n
                            1) Odoo Default Tax Behaviour - The Taxes will be set based on Odoo's
                                         default functional behaviour i.e. based on Odoo's Tax and Fiscal Position configurations. \n
                            2) Create WooCommerce Tax If Not Found - System will search the tax data received 
                            from Woocommerce in Odoo, will create a new one if it fails in finding it.""")
    woocommerce_create_product_if_not_found = fields.Boolean('Create Product in Odoo if not matched.', default=False)
    is_sync_wc_images = fields.Boolean("Sync Product Images?",
                                       help="If true then Images will be sync at the time of Import Products.",
                                       default=False)

    def action_test_connection(self):
        instance = self
        self.env['woocommerce.payment.gateway'].import_woocommerce_payment_gateway(self)
        self.env['woocommerce.shipping.method'].import_shipping_method(self)
        self.env['woocommerce.customer.data.queue'].import_customers_from_woocommerce_to_odoo(self)
        self.env['woocommerce.product.category'].import_product_category(self)
        self.env['woocommerce.product.tags'].import_product_tags(self)
        self.setup_woocommerce_export_stock_cron()
        message = _("Connection Test Succeeded!")
        return {
            'effect': {
                'fadeout': 'slow',
                'message': message,
                'img_url': '/web/static/img/smile.svg',
                'type': 'rainbow_man',
            }
        }

    def create_cron_for_automation_task(self, cron_name, model_name, code_method, interval_number=10,
                                        interval_type='minutes', numbercall=1, nextcall_timegap_minutes=10):
        """
        This method is used for create cron record.
        """
        self.env['ir.cron'].create({
            'name': cron_name,
            'model_id': self.env['ir.model'].search([('model', '=', model_name)]).id,
            'state': 'code',
            'code': code_method,
            'interval_number': interval_number,
            'interval_type': interval_type,
            'numbercall': numbercall,
            'nextcall': datetime.now() + timedelta(minutes=nextcall_timegap_minutes),
            'doall': True,
            'woocommerce_instance': self.id
        })
        return True

    def setup_woocommerce_export_stock_cron(self):
        """
        From this method export stock cron creation process declared.
        """
        code_method = 'model.prepare_export_stock_data_for_woocommerce({0})'.format(self.id)
        existing_cron = self.env['ir.cron'].search([('code', '=', code_method), ('active', 'in', [True, False])])
        if existing_cron:
            return True
        cron_name = "Woocommerce: [{0}] Prepare export stock data for Woocommerce".format(self.name)
        model_name = 'woocommerce.instance.integration'
        # code_method = 'model.prepare_export_stock_data_for_shopify({0})'.format(self.id)
        self.create_cron_for_automation_task(cron_name, model_name, code_method,
                                             interval_type='minutes', interval_number=40,
                                             numbercall=1, nextcall_timegap_minutes=20)
        return True

    def woocommerce_api_calling_process(self, request_type=False, api_url=False, request_data=False, params=False):
        data = "%s:%s" % (self.woocommerce_key,
                          self.woocommerce_secret)
        encode_data = base64.b64encode(data.encode("utf-8"))
        authrization_data = "Basic %s" % (encode_data.decode("utf-8"))
        headers = {
            'Authorization': authrization_data,
            "Content-Type": "application/json"
        }
        _logger.info("Shipment Request API URL:::: %s" % api_url)
        _logger.info("Shipment Request Data:::: %s" % request_data)
        response_data = requests.request(method=request_type, url=api_url, headers=headers, data=request_data,
                                         params=params, verify=False)
        next_page_link = response_data.links and response_data.links.get('next', {}).get('url')
        if response_data.status_code in [200, 201]:
            response_data = response_data.json()
            _logger.info(">>> Response Data {}".format(response_data))
            return True, response_data, next_page_link
        else:
            return False, response_data.text, next_page_link

    def get_stock_updates(self):
        """
        This method is used to fetch odoo product in which last stock updated in last 3 hours.
        """
        to_date = datetime.now()
        date = to_date - timedelta(hours=3)
        query = """SELECT product_id FROM stock_move WHERE date >= %s AND
                   state IN ('partially_available', 'assigned', 'done')"""
        self.env.cr.execute(query, (date,))
        result = self.env.cr.fetchall()
        return [item[0] for item in result]



    def prepare_export_stock_data_for_woocommerce(self, instance):
        """
        Prepare export stock data for WooCommerce for both variants and simple products.
        Stores product_id, woocommerce_product_id, stock_quantity, product_type, and parent_product_id
        in inventory_data_to_process.
        """
        instance_id = self.env['woocommerce.instance.integration'].browse(instance)
        _logger.info("Starting WooCommerce stock export for instance: %s", instance_id.name)

        # Create log
        log_id = self.env['woocommerce.log'].generate_woocommerce_logs(
            woocommerce_operation_name='inventory',
            woocommerce_operation_type='export',
            instance=instance_id,
            woocommerce_operation_message='Process Started'
        )

        # Get products with stock updates in last 3 hours
        updated_odoo_product_ids = self.get_stock_updates()
        if not updated_odoo_product_ids:
            _logger.info("No stock updates found for export.")
            return True

        _logger.info("Odoo Products to export => %s", updated_odoo_product_ids)

        queue_line_data = []
        already_handled_ids = []

        # 1️⃣ Handle variant products (listing items)
        listing_items = self.env['woocommerce.product.listing.item'].search([
            ('product_id', 'in', updated_odoo_product_ids),
            ('woocommerce_instance_id', '=', instance_id.id)
        ])

        for item in listing_items:
            product = item.product_id
            actual_stock = getattr(product, 'free_qty', 0)


            queue_line_data.append({
                'product_id': product.id,
                'woocommerce_product_id': getattr(item, 'woocommerce_product_variant_id', False),
                'stock_quantity': actual_stock,
                'available': actual_stock,
                'product_type': 'variant',
                'parent_product_id': getattr(item.woocommerce_product_listing_id, 'woocommerce_product_id', False)
            })
            already_handled_ids.append(product.id)

        # 2️⃣ Handle simple products (listing table)
        listings = self.env['woocommerce.product.listing'].search([
            ('product_tmpl_id.product_variant_ids.id', 'in', updated_odoo_product_ids)
        ])

        for listing in listings:
            product_variants = listing.product_tmpl_id.product_variant_ids.filtered(
                lambda p: p.id in updated_odoo_product_ids and p.id not in already_handled_ids
            )
            for product in product_variants:
                actual_stock = getattr(product, 'free_qty', 0)

                # Default stock_type/stock_value for simple products
                class DummyListing:
                    stock_type = 'none'
                    stock_value = 0

                queue_line_data.append({
                    'product_id': product.id,
                    'woocommerce_product_id': getattr(listing, 'woocommerce_product_id', False),
                    'stock_quantity': actual_stock,
                    'available': actual_stock,
                    'product_type': 'simple',
                    'parent_product_id': False
                })
                already_handled_ids.append(product.id)

        if not queue_line_data:
            message = "No products found to create WooCommerce inventory queue."
            _logger.info(message)
            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                'inventory', 'export', instance_id, message, False, message, log_id, True
            )
            self._cr.commit()
            return False

        # Create queue
        queue_id = self.env['woocommerce.inventory.data.queue'].create({'instance_id': instance_id.id})

        # Prepare list of values to create all queue lines in one call
        create_vals = []
        for line in queue_line_data:
            create_vals.append({
                'product_id': line['product_id'],
                'inventory_data_to_process': json.dumps({
                    "woocommerce_product_id": line['woocommerce_product_id'],
                    "stock_quantity": line['stock_quantity'],
                    "available": line['available'],
                    "product_type": line['product_type'],
                    "parent_product_id": line['parent_product_id']
                }),
                'state': 'draft',
                'instance_id': instance_id.id,
                'woocommerce_inventory_queue_id': queue_id.id,
            })

        if create_vals:
            self.env['woocommerce.inventory.data.queue.line'].create(create_vals)

        # Remove empty log if no lines were created
        if not log_id.woocommerce_operation_line_ids:
            log_id.unlink()

        _logger.info("WooCommerce stock queue created successfully for %d products.", len(queue_line_data))
        return True

