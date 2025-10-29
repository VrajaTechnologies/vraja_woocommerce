from odoo import models, fields


class WoocommerceTaxes(models.Model):
    _name = "woocommerce.taxes"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'WooCommerce Taxes'
    _rec_name =  'woocommerce_tax_name'

    woocommerce_tax_id = fields.Integer("WooCommerce Tax ID", copy=False)
    woocommerce_tax_name = fields.Char(string="WooCommerce Tax Name", copy=False)
    woocommerce_tax_rate = fields.Float(string="WooCommerce Tax Rate", copy=False)
    woocommerce_tax_class = fields.Char(string="WooCommerce Tax Class", copy=False)
    woocommerce_country_id = fields.Many2one('res.country', string="Country", copy=False)
    instance_id = fields.Many2one('woocommerce.instance.integration', string="WooCommerce Instance", copy=False)
    company_id = fields.Many2one('res.company', string="Company", copy=False)

    def import_woocommerce_taxes(self, instance):
        """
        This method imports tax rates from WooCommerce into Odoo.
        """
        try:
            log_id = self.env['woocommerce.log'].generate_woocommerce_logs(
                'tax', 'import', instance, 'WooCommerce Tax Import Process Started'
            )

            api_url = f"{instance.woocommerce_url}/wp-json/wc/v3/taxes"
            response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("GET", api_url)

            if response_status:
                for tax_response in response_data:
                    self.search_or_create_woocommerce_tax(instance, tax_response, log_id)

                log_id.woocommerce_operation_message = "WooCommerce Tax Import Completed Successfully"
            else:
                message = "Error while fetching tax rates from WooCommerce"
                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                    'tax', 'import', instance, message, False, response_data, log_id, True
                )
        except Exception as error:
            message = "Unexpected error occurred during WooCommerce tax import"
            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                'tax', 'import', instance, message, False, str(error), log_id, True
            )

    def search_or_create_woocommerce_tax(self, instance, tax_response, log_id):
        """
        Search for existing WooCommerce tax and create/update it in custom model.
        """
        wc_tax_id = str(tax_response.get('id'))
        name = tax_response.get('name')
        rate = float(tax_response.get('rate') or 0.0)
        tax_class = tax_response.get('class') or 'standard-rate'
        country_code = tax_response.get('country') or False

        country_id = False
        if country_code:
            country_id = self.env['res.country'].search([('code', '=', country_code)], limit=1).id

        # Check existing WooCommerce tax record
        existing_tax = self.search([
            ('woocommerce_tax_id', '=', wc_tax_id),
            ('instance_id', '=', instance.id)
        ], limit=1)

        if not existing_tax:
            self.create({
                'woocommerce_tax_id': wc_tax_id,
                'woocommerce_tax_name': name,
                'woocommerce_tax_rate': rate,
                'woocommerce_tax_class': tax_class,
                'woocommerce_country_id': country_id,
                'instance_id': instance.id,
                'company_id': instance.company_id.id,
            })
            msg = f"WooCommerce Tax '{name}' created successfully ({rate}%)"
        else:
            existing_tax.write({
                'woocommerce_tax_rate': rate,
                'woocommerce_tax_name': name,
                'woocommerce_tax_class': tax_class,
                'woocommerce_country_id': country_id,
            })
            msg = f"WooCommerce Tax '{name}' updated ({rate}%)"

        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
            'tax', 'import', instance, msg, False, tax_response, log_id, False
        )
