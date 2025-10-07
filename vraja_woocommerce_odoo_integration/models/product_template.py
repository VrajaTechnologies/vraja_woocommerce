from odoo import fields,models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def export_product_instance_wizard(self):
        return {
            'name': 'Export Product To Woocommerce Instance',
            'type': 'ir.actions.act_window',
            'res_model': 'prepare.product.for.export.woocommerce.instance',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': self.ids},
        }