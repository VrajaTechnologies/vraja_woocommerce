import logging
import requests
import base64
from odoo import models, fields,api
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

    woocommerce_last_synced_order_date = fields.Datetime(string="Last Sync Order Date",copy=False)
    woocommerce_last_product_synced_date = fields.Datetime(string="Last Sync Order Date",copy=False)
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
        # self.env['woocommerce.payment.gateway'].import_payment_gateway(self)
        # self.env['woocommerce.shipping.method'].import_shipping_method(self)
        # self.env['woocommerce.customer.data.queue'].import_customers_from_woocommerce_to_odoo(self)
        # self.env['woocommerce.product.category'].import_product_category(self)
        # self.env['woocommerce.product.tags'].import_product_tags(self)

    def woocommerce_api_calling_process(self, request_type=False, api_url=False, request_data=False, params=False):
        data = "%s:%s" % (self.woocommerce_key,
                          self.woocommerce_secret)
        encode_data = base64.b64encode(data.encode("utf-8"))
        authrization_data = "Basic %s" % (encode_data.decode("utf-8"))
        headers = {
            'Authorization': authrization_data
        }
        _logger.info("Shipment Request API URL:::: %s" % api_url)
        _logger.info("Shipment Request Data:::: %s" % request_data)
        response_data = requests.request(method=request_type, url=api_url, headers=headers, data=request_data,
                                         params=params,verify=False)
        next_page_link = response_data.links and response_data.links.get('next',{}).get('url')
        if response_data.status_code in [200, 201]:
            response_data = response_data.json()
            _logger.info(">>> Response Data {}".format(response_data))
            return True, response_data,next_page_link
        else:
            return False, response_data.text,next_page_link
