import logging
from odoo import fields, models,api

_logger = logging.getLogger("WooCommerce")


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'
    _description = "Woocommerce Delivery Data"

    woocommerce_delivery_code = fields.Char(string="Woocommerce Delivery Code", copy=False,
                                            help="This fields value used for check woocommerce delivery code")
    woocommerce_shipping_method_id = fields.Many2one('woocommerce.shipping.method', help="WooCommerce Shipping Methods")

    @api.depends('woocommerce_shipping_method_id')
    def _set_woocommerce_shipping_code(self):
        self.write({'woocommerce_delivery_code': self.woocommerce_shipping_method_id.name})
