from odoo import models, fields


class WoocommerceFinancialStatusConfiguration(models.Model):
    _name = 'woocommerce.financial.status.configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Woocommerce Financial Status Configuration'

    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance')
    company_id = fields.Many2one('res.company', string='Company', help='Select Company', default=lambda self: self.env.user.company_id)
    payment_gateway_id = fields.Many2one('woocommerce.payment.gateway', string='Payment Gateway',
                                         help='Select Payment')
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term', help='Select Payment Term',
                                      default=lambda self: self.env.ref('account.account_payment_term_immediate'))
    sale_auto_workflow_id = fields.Many2one('woocommerce.order.workflow.automation', string='Auto Workflow',
                                            help='Select Workflow')
    active = fields.Boolean(string='Active', default=True)
    financial_status = fields.Selection([
        ('paid', 'The finances have been paid'),
        ('not_paid', 'The finances have been not paid')
    ], string='Financial Status', help='Select Financial Status')

    def create_woocommerce_financial_status(self, instance, woocommerce_financial_status):
        """
        Creates woocommerce financial status for payment methods of instance.
        @param instance: woocommerce_instance
        @param woocommerce_financial_status: Status as paid or not paid.
        """
        payment_methods = self.env['woocommerce.payment.gateway'].search([('instance_id', '=', instance.id)])
        journal_id = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)

        auto_workflow_obj = self.env['woocommerce.order.workflow.automation']
        auto_workflow_id = auto_workflow_obj.search([('name', '=', 'Automatic Validation')])
        if not auto_workflow_id:
            auto_workflow_id = auto_workflow_obj.create({
                'name': 'Automatic Validation',
                'journal_id': journal_id.id,
                'company_id': instance.company_id.id
            })

        for payment_method in payment_methods:
            # Check record already exist or not
            existing_woocommerce_financial_status = self.search([('instance_id', '=', instance.id),
                                                             ('payment_gateway_id', '=', payment_method.id),
                                                             ('financial_status', '=', woocommerce_financial_status)]).ids
            if existing_woocommerce_financial_status:
                continue

            # Create new record based on payment methods
            self.create({
                'instance_id': instance.id,
                'sale_auto_workflow_id': auto_workflow_id.id,
                'payment_gateway_id': payment_method.id,
                'financial_status': woocommerce_financial_status,
                'company_id': instance.company_id.id
            })
        return True
