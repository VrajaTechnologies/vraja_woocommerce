from odoo import fields,models

class ExportWoocommerceProduct(models.TransientModel):
    _name = "export.woocommerce.product"
    _description = "Woocommerce Product Export Wizard"

    set_price = fields.Boolean(string="Set Price")
    set_image = fields.Boolean(string="Set Image")

    def export_woocommerce_product(self):
        pass