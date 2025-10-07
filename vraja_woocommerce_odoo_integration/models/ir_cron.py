from odoo import models, fields


class IrCron(models.Model):
    _inherit = 'ir.cron'

    woocommerce_instance = fields.Many2one('woocommerce.instance.integration')
