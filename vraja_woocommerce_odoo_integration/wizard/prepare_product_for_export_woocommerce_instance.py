from odoo import fields,models

class PrepreProductForExportWoocommerceInstance(models.TransientModel):
    _name = "prepare.product.for.export.woocommerce.instance"
    _description = "Export Product Woocommerce Instance Wizard"

    woocommerce_instance = fields.Many2one('woocommerce.instance.integration',string="Woocomerce Instance")
    def prepare_product_for_export_woocommerce_instance(self):
        """export products from """
        pass