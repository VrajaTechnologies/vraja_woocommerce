from odoo import models,fields

class UpdateWoocommerceProduct(models.TransientModel):
    _name = "update.woocommerce.product"

    set_price = fields.Boolean(string="Set Price")
    set_image = fields.Boolean(string="Set Image")

    def update_woocommerce_product(self):
        pass