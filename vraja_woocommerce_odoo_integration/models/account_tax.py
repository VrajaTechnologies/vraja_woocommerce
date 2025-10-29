from odoo import models, fields

class AccountTax(models.Model):
    _inherit = 'account.tax'

    woocommerce_tax_id = fields.Many2one(comodel_name="woocommerce.taxes",string="Woocommerce Tax")