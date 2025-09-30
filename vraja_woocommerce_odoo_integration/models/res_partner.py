from odoo import models, fields


class SalesOrder(models.Model):
    _inherit = 'res.partner'

    woocommerce_customer_id = fields.Char(string="WooCommerce Customer ID",
                                          help="This is just a reference of WooCommerce customer identifier")
    woocommerce_instance_id = fields.Many2one('woocommerce.instance.integration', string="Woocommerce Instance",
                                              help="This field show the instance details of Woocommerce", tracking=True)

    def prepare_customer_vals(self, address, customer_id=False, type=False):
        country_id = self.env['res.country'].search([('code', '=', address.get('country'))])
        state_id = self.env['res.country.state'].search(
            [('code', '=', address.get('state')), ('country_id', '=', country_id.id)])
        customer_vals = {
            'name': "{0} {1}".format(address.get('first_name', '') or '',
                                     address.get('last_name', '') or ''),
            'street': address.get('address_1', ''),
            'street2': address.get('address_2', ''),
            'city': address.get('city', ''),
            'zip': address.get('postcode', ''),
            'email': address.get('email') or '',
            'phone': address.get('phone') or '',
            'type': type,
            'country_id': country_id.id or '',
            'state_id': state_id.id or '',
            'parent_id': customer_id.id,
        }
        return customer_vals

    def create_update_customer_in_odoo(self, customer_vals, woocommerce_customer_id):
        partner_obj = self.env["res.partner"]
        customer_id = False
        if self._context.get('type') == 'delivery' or self._context.get('type') == 'invoice':
            existing_customer = self.env['res.partner'].search(
                [('type', '=', self._context.get('type')), ('parent_id', '=', self._context.get('parent').id)],
                limit=1)
        else:
            existing_customer = self.env['res.partner'].search(
                [('woocommerce_customer_id', '=', woocommerce_customer_id)],
                limit=1)
        try:
            if existing_customer:
                existing_customer.write(customer_vals)
                customer_id = existing_customer
                msg, fault, line_state = "Customer {0} Updated Successfully".format(
                    customer_vals.get('name')), False, 'completed'
            else:
                customer_id = partner_obj.create(customer_vals)
                msg, fault, line_state = "Customer {0} Created Successfully".format(
                    customer_vals.get('name')), False, 'completed'
        except Exception as error:
            msg, fault, line_state = "Getting Some error While create or update customer in odoo {0} - {1}".format(
                customer_vals.get('name'), error), True, 'failed'
        return customer_id, msg, fault, line_state

    def create_update_customer_woocommerce_to_odoo(self, log_id, instance_id=False, customer_data=False,
                                                   so_customer_data=False):
        customer_datas = so_customer_data or customer_data
        woocommerce_customer_id = customer_datas.get('id')
        customer_vals = {'name': "{0} {1}".format(customer_datas.get('first_name', '') or '',
                                                  customer_datas.get('last_name', '') or ''),
                         'email': customer_datas.get('email'),
                         'woocommerce_customer_id': woocommerce_customer_id,
                         'woocommerce_instance_id': instance_id.id if instance_id else False
                         }
        customer_id, msg, fault, line_state = self.create_update_customer_in_odoo(customer_vals,
                                                                                  woocommerce_customer_id)
        # for address_data in customer_datas.get('addresses'):
        if customer_id and customer_datas.get('shipping') and customer_datas.get('shipping').get('address_1'):
            shipping_address = customer_datas.get('shipping')
            customer_vals = self.prepare_customer_vals(shipping_address, customer_id, type='delivery')
            self.with_context(type='delivery', parent=customer_id).create_update_customer_in_odoo(customer_vals,
                                                                                                  woocommerce_customer_id)

        if customer_datas.get('billing') and customer_datas.get('billing').get('address_1'):
            billing_address = customer_datas.get('billing')
            customer_vals = self.prepare_customer_vals(billing_address, customer_id, type='invoice')
            self.with_context(type='invoice', parent=customer_id).create_update_customer_in_odoo(customer_vals,
                                                                                                 woocommerce_customer_id)
        return customer_id, msg, fault, line_state
