from odoo import fields,models

class ExportWoocommerceProduct(models.TransientModel):
    _name = "update.woocommerce.product"
    _description = "Woocommerce Product Export and Update Wizard"

    set_price = fields.Boolean(string="Set Price")
    set_image = fields.Boolean(string="Set Image")

    def update_woocommerce_product(self):
        pass