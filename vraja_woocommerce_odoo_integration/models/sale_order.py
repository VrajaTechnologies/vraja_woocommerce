from odoo import models, fields, tools, _
import pytz
import re
import logging
import time
from dateutil import parser

utc = pytz.utc

_logger = logging.getLogger("Woocommerce")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    instance_id = fields.Many2one('woocommerce.instance.integration', string="Instance", copy=False)
    woocommerce_order_number = fields.Char(string="Woocommerce Order Number", copy=False,
                                           help="This is the represent the number of Woocommerce order")
    woocommerce_order_id = fields.Char("Woo Order Reference", help="WooCommerce Order Reference", copy=False)
    woocommerce_sale_auto_workflow_id = fields.Many2one('woocommerce.order.workflow.automation',
                                                        'WooCommerce Auto Workflow')
    payment_gateway_id = fields.Many2one('woocommerce.payment.gateway', string="Payment Method")

    def find_create_woocommerce_customer_in_odoo(self, instance_id, woocommerce_order_dictionary, log_id=False,
                                                 line=False):
        """
        This method was used for search or create customer in odoo if we have not found customer in odoo then
        we call the api and create that customer in odoo
        @param : instance_id : object of instance
                 woocommerce_order_dict : json response of woocommerce sale order response
        @return : if not found customer id in response then return false otherwise return customer id
        """

        woocommerce_customer_id = woocommerce_order_dictionary.get('customer_id')
        if not woocommerce_customer_id:
            return False
        odoo_customer_id = self.env['res.partner'].search([('woocommerce_customer_id', '=', woocommerce_customer_id)])
        if odoo_customer_id:
            return odoo_customer_id
        else:
            try:
                customer_data = self.env['woocommerce.customer.data.queue'].fetch_customers_from_woocommerce_to_odoo(
                    instance_id, from_date=False, to_date=False, customer_id=woocommerce_customer_id)
                if customer_data:
                    customer_id = self.env['res.partner'].create_update_customer_woocommerce_to_odoo(log_id,
                                                                                                     customer_data=False,
                                                                                                     so_customer_data=customer_data,
                                                                                                     instance_id=instance_id)
                    print(customer_id)
                    return customer_id
            except Exception as e:
                _logger.info(e)
            # so_customer_data = shopify_customer_data.to_dict()
            # customer_id = self.env['res.partner'].create_update_customer_shopify_to_odoo(instance_id=instance_id,
            #                                                                              so_customer_data=so_customer_data,
            #                                                                              log_id=log_id)
            # return customer_id

    def get_price_list(self, currency_id, instance_id):
        price_list_object = self.env['product.pricelist']
        price_list_id = instance_id.woocommerce_price_list_id or False
        if not price_list_id:
            price_list_id = price_list_object.search([('currency_id', '=', currency_id.id)], limit=1)
        return price_list_id

    def create_or_update_payment_gateway_and_workflow(self, woocommerce_order_dictionary, instance_id, line):
        woocommerce_financial_status_object = self.env["woocommerce.financial.status.configuration"]
        payment_gateway_obj = self.env["woocommerce.payment.gateway"]
        try:
            # below code was used for find financial status from order response
            if (woocommerce_order_dictionary.get("transaction_id")) or (
                    woocommerce_order_dictionary.get("date_paid") and woocommerce_order_dictionary.get(
                "payment_method") != "cod" and woocommerce_order_dictionary.get(
                "status") == "processing"):
                financial_status = "paid"
            else:
                financial_status = "not_paid"

            # below code was used for find payment gateway object
            code = woocommerce_order_dictionary.get("payment_method", "")
            name = woocommerce_order_dictionary.get("payment_method_title", "")
            if not code:
                code = "no_payment_method"
                name = "No Payment Method"

            # Check order for full discount, when there is no payment gateway found.
            total_discount = 0
            total = woocommerce_order_dictionary.get("total")
            if woocommerce_order_dictionary.get("coupon_lines"):
                total_discount = woocommerce_order_dictionary.get("discount_total")
            if float(total) == 0 and float(total_discount) > 0:
                no_payment_gateway = True
            else:
                no_payment_gateway = False

            # based on payment gateway we found financial status using below code
            if no_payment_gateway:
                payment_gateway = payment_gateway_obj.search([("code", "=", "no_payment_method"),
                                                              ("instance_id", "=", instance_id.id)])
                woocommerce_financial_status = woocommerce_financial_status_object.search(
                    [("instance_id", "=", instance_id.id),
                     ("financial_status", "=",
                      financial_status),
                     ("payment_gateway_id", "=",
                      payment_gateway.id)],
                    limit=1)
            else:
                payment_gateway = payment_gateway_obj.search_or_create_woocommerce_payment_gateway(instance_id,
                                                                                                   code=code,
                                                                                                   name=name)
                woocommerce_financial_status = woocommerce_financial_status_object.search(
                    [('instance_id', '=', instance_id.id), ('payment_gateway_id.name', '=', payment_gateway.name),
                     ('financial_status', '=', financial_status)], limit=1)

            if not woocommerce_financial_status:
                message = "We cant find financial status for order number- {0}".format(
                    woocommerce_order_dictionary.get("number"))
                return False, None, message, True, 'failed'

            if not woocommerce_financial_status.sale_auto_workflow_id.policy_of_picking:
                message = "We cant find policy of picking in sale auto workflow - {0} for order {1}".format(
                    woocommerce_financial_status.sale_auto_workflow_id, woocommerce_order_dictionary.get("number"))
                return False, None, message, True, 'failed'
            return True, woocommerce_financial_status, "Financial status found successfully", False, 'completed'
        except Exception as e:
            msg = "Unexpected error finding financial status for order {0}: {1}".format(
                woocommerce_order_dictionary.get("number"), str(e)
            )
            return False, None, msg, True, 'failed'

    def prepare_vals_for_sale_order_line(self, price, quantity, product_id, sale_order_id,
                                         is_delivery=False):

        vals = {
            'order_id': sale_order_id.id,
            'product_id': product_id.id,
            'product_uom_qty': quantity,
            'price_unit': price,
            'is_delivery': is_delivery,
        }
        return vals

    def get_sku_from_woocommerce_sources(self, order_line_data, instance_id, log_id, sale_order_id,
                                         woocommerce_order_dictionary):
        """
        Find SKU from:
        1) Order line
        2) Listing Item (variant first, fallback to product)
        3) Import product if needed
        """

        wc_product_id = order_line_data.get("product_id")
        wc_variant_id = order_line_data.get("variation_id")
        product_sku = order_line_data.get("sku")

        ProductListingItem = self.env['woocommerce.product.listing.item']
        ProductListing = self.env['woocommerce.product.listing']

        # ---------------------------------------------------
        # ✅ STEP 1: SKU already in order line
        # ---------------------------------------------------
        if product_sku:
            return product_sku

        # ---------------------------------------------------
        # ✅ STEP 2: Try from listing items
        # ---------------------------------------------------
        listing_item = False

        # Try variant_id first
        if wc_variant_id and wc_variant_id != 0:
            listing_item = ProductListingItem.search([
                ('woocommerce_product_variant_id', '=', wc_variant_id)
            ], limit=1)

        # Fallback: try product_id
        if not listing_item:
            listing_item = ProductListingItem.search([
                ('woocommerce_product_listing_id.woocommerce_product_id', '=', wc_product_id)
            ], limit=1)

        # Found SKU
        if listing_item and listing_item.product_sku:
            return listing_item.product_sku

        # ---------------------------------------------------
        # ✅ STEP 3: Import product because SKU still missing
        # ---------------------------------------------------
        sale_order_id.message_post(
            body=f"SKU missing for '{order_line_data.get('name')}'. Attempting product import...")

        product_listing = ProductListing.woocommerce_create_products(
            product_queue_line=False,
            instance=instance_id,
            log_id=log_id,
            order_line_product_listing_id=wc_product_id
        )

        # If import failed → return False
        if not product_listing:
            return False

        # ---------------------------------------------------
        # ✅ STEP 4: Retry finding SKU after product import
        # ---------------------------------------------------

        # Try variant
        if wc_variant_id and wc_variant_id != 0:
            listing_item = ProductListingItem.search([
                ('woocommerce_product_variant_id', '=', wc_variant_id)
            ], limit=1)

        # Try product
        if not listing_item:
            listing_item = ProductListingItem.search([
                ('woocommerce_product_listing_id.woocommerce_product_id', '=', wc_product_id)
            ], limit=1)

        return listing_item.product_sku if listing_item and listing_item.product_sku else False

    def create_woocommerce_sale_order_line(self, sale_order_id, woocommerce_order_dictionary, woocommerce_taxes,
                                           instance_id, log_id=False, order_queue_line=False):

        woocommerce_order_lines = woocommerce_order_dictionary.get("line_items")
        if isinstance(woocommerce_order_lines, dict):
            woocommerce_order_lines = [woocommerce_order_lines]

        message = ''
        skip_auto_workflow = False
        Product = self.env['product.product']

        for order_line_data in woocommerce_order_lines:

            # ✅ Get SKU using helper method
            product_sku = self.get_sku_from_woocommerce_sources(
                order_line_data, instance_id, log_id, sale_order_id, woocommerce_order_dictionary
            )

            # ✅ If still no SKU → skip
            if not product_sku:
                msg = (
                    "Skipping order line for '{0}' in order {1} because SKU could not be found."
                ).format(order_line_data.get('name'), woocommerce_order_dictionary.get('id'))

                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                    'order', 'import', instance_id, msg, False,
                    woocommerce_order_dictionary, log_id, True
                )
                sale_order_id.message_post(body=msg)
                skip_auto_workflow = True
                continue

            # ✅ Find product in Odoo
            product_id = Product.search([("default_code", "=", product_sku)], limit=1)

            # ✅ Re-import product if not found after SKU obtained
            if not product_id:
                self.env['woocommerce.product.listing'].woocommerce_create_products(
                    product_queue_line=False, instance=instance_id, log_id=log_id,
                    order_line_product_listing_id=order_line_data.get('product_id')
                )
                product_id = Product.search([("default_code", "=", product_sku)], limit=1)

            # ✅ Final check
            if not product_id:
                msg = "Product {0} - {1} not found for Order {2}".format(
                    product_sku, order_line_data.get("name"), woocommerce_order_dictionary.get('number')
                )
                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                    'order', 'import', instance_id, msg, False,
                    woocommerce_order_dictionary, log_id, True
                )
                sale_order_id.message_post(body=msg)
                skip_auto_workflow = True
                continue

            # ✅ Prepare SO line
            order_line_vals = self.prepare_vals_for_sale_order_line(
                order_line_data.get('total'),
                order_line_data.get('quantity'),
                product_id,
                sale_order_id
            )

            # ✅ Taxes
            if order_line_data.get('taxes'):
                line_taxes = []
                for taxes in order_line_data.get('taxes'):
                    tax = self.env['account.tax'].search([
                        ('woocommerce_tax_id.woocommerce_tax_id', '=', taxes.get('id'))
                    ], limit=1)
                    if tax:
                        line_taxes.append(tax.id)
                    else:
                        skip_auto_workflow = True
                        order_queue_line.state = 'failed'
                        err = f"WooCommerce Tax ID {taxes.get('id')} not found in Odoo."
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'order', 'import', instance_id, err, False, err, log_id, True
                        )

                if line_taxes:
                    order_line_vals["tax_id"] = [(6, 0, line_taxes)]

            sale_order_line = self.env['sale.order.line'].create(order_line_vals)

            # ✅ Set description
            desc = []
            if sale_order_line.name:
                desc.append(sale_order_line.name)
            if order_line_data.get('name'):
                desc.append(order_line_data.get('name'))

            discount_total = float(order_line_data.get('subtotal')) - float(order_line_data.get('total'))
            if discount_total > 0:
                desc.append(f"Discount applied: -{discount_total:.2f}")

            sale_order_line.name = "\n".join([d for d in desc if d])
            sale_order_line.with_context(round=False)._compute_amount()

        return True, message, False, 'draft', skip_auto_workflow

    def convert_woocommerce_order_date(self, order_response):
        if order_response.get("date_created", False):
            order_date = order_response.get("date_created", False)
            date_order = parser.parse(order_date).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
        else:
            date_order = time.strftime("%Y-%m-%d %H:%M:%S")
            date_order = str(date_order)
        return date_order

    def woocommerce_prepare_tax_data(self, woocommerce_order_dictionary, line, instance_id, woocommerce_taxes):
        rate_percent = ""

        for order_tax in woocommerce_order_dictionary.get('tax_lines'):
            if order_tax.get('rate_id') in woocommerce_taxes.keys():
                continue
            if not rate_percent:
                if 'rate_percent' in order_tax.keys():
                    rate_percent = "available"
                else:
                    rate_percent = "not available"

            if rate_percent == "available":
                woocommerce_taxes.update({order_tax.get('rate_id'): {"name": order_tax.get('label'),
                                                                     "rate": order_tax.get('rate_percent')}})
            elif rate_percent == "not available":
                params = {"_fields": "id,name,rate"}
                try:
                    url = "{0}/wp-json/wc/v3/taxes/{1}".format(instance_id.woocommerce_url, params)
                    response_status, response_data, next_page_link = instance_id.woocommerce_api_calling_process("GET",
                                                                                                                 url)
                    tax_data = response_data
                except Exception:
                    _logger.info(response_data)
                woocommerce_taxes.update({tax_data["id"]: tax_data})
                if isinstance(woocommerce_taxes, str):
                    message = "Order #%s not imported due to missing tax information.\nTax rate id: %s and Tax " \
                              "label: %s is deleted after order creation in WooCommerce " \
                              "store." % (woocommerce_order_dictionary.get('number'),
                                          woocommerce_order_dictionary.get('rate_id'),
                                          woocommerce_order_dictionary.get('label'))

                    return False
        return woocommerce_taxes

    def search_or_create_delivery_carrier(self, shipping_product_id, delivery_method, shipping_line):
        delivery_carrier_object = self.env["delivery.carrier"]
        shipping_method_object = self.env['woocommerce.shipping.method']
        carrier = delivery_carrier_object.search([("woocommerce_delivery_code", "=", delivery_method)], limit=1)
        woocommerce_shipping_method = shipping_method_object.search([("name", "ilike", delivery_method)],
                                                                    limit=1)
        if not carrier:
            carrier = delivery_carrier_object.search([("name", "=", delivery_method)], limit=1)
        if not carrier:
            carrier = delivery_carrier_object.search(["|", ("name", "ilike", delivery_method),
                                                      ("woocommerce_delivery_code", "ilike", delivery_method)], limit=1)
        if not carrier:
            carrier = delivery_carrier_object.create(
                {"name": delivery_method, "woocommerce_delivery_code": delivery_method,
                 "woocommerce_shipping_method_id": woocommerce_shipping_method.id,
                 "fixed_price": shipping_line.get("total"),
                 "product_id": shipping_product_id.id})
        return carrier

    def woocommerce_create_shipping_fee_coupon_lines(self, instance_id, woocommerce_order_dictionary, tax_included,
                                                     woo_taxes, sale_order_id):

        # below code was used for create shipping line
        shipping_product_id = instance_id.woocommerce_shipping_product_id
        for shipping_line in woocommerce_order_dictionary.get("shipping_lines"):
            delivery_method = shipping_line.get("method_title")
            if delivery_method:
                carrier = self.search_or_create_delivery_carrier(shipping_product_id, delivery_method, shipping_line)
                shipping_product = carrier.product_id
                self.write({"carrier_id": carrier.id})

                # taxes = []
                # if self.woo_instance_id.apply_tax == "create_woo_tax":
                #     taxes = [woo_taxes.get(tax["id"]) for tax in shipping_line.get("taxes") if tax.get("total")]

                total_shipping = float(shipping_line.get("total", 0.0))
                if tax_included:
                    total_shipping += float(shipping_line.get("total_tax", 0.0))
                shipping_line_vals = self.prepare_vals_for_sale_order_line(total_shipping, 1, shipping_product,
                                                                           sale_order_id, True)
                shipping_line_id = self.env['sale.order.line'].create(shipping_line_vals)
                _logger.info("Shipping line is created for the sale order: %s.", self.name)

        # below code was used for add fee line in sale order
        for fee_line in woocommerce_order_dictionary.get("fee_lines"):
            if tax_included:
                total_fee = float(fee_line.get("total", 0.0)) + float(fee_line.get("total_tax", 0.0))
            else:
                total_fee = float(fee_line.get("total", 0.0))
            if total_fee:
                taxes = []
                # if instance_id.apply_tax == "create_woo_tax":
                #     taxes = [woo_taxes.get(tax["id"]) for tax in fee_line.get("taxes") if tax.get("total")]

                fee_line_vals = self.prepare_vals_for_sale_order_line(total_fee, 1,
                                                                      instance_id.woocommerce_fee_product_id,
                                                                      sale_order_id, True)
                # fee_line_vals.update({'price_unit': total_fee})
                fee_line_id = self.env['sale.order.line'].create(fee_line_vals)
                _logger.info("Fee line is created for the sale order %s.", self.name)
        return True

    def auto_confirm_woocommerce_sale_order(self, sale_order_id):
        """
        This method used for confirm sale order automatically if permission was granted in sale auto workflow for
        confirm sale order
        @param : instance_id : object of instance
                sale_order_id :object of created sale order
                log_id : object of main log
                line : object of log line
        """
        try:
            date_order = sale_order_id.date_order
            sale_order_id.action_confirm()
            sale_order_id.date_order = date_order
            return True, False, False, 'draft'
        except Exception as e:
            error_msg = 'Can not confirm sale order {0} \n Error: {1}'.format(sale_order_id.name, e)
            return False, error_msg, True, 'failed'

    def auto_validate_woocommerce_delivery_order(self, sale_order_id):
        """This method was used for validate delivery order based on sale auto work flow permission
                 @param : instance_id : object of instance
                        sale_order_id :object of created sale order
                        log_id : object of main log
                        line : object of log line
                """
        try:
            for picking_id in sale_order_id.picking_ids:
                for move_id in picking_id.move_ids_without_package:
                    # if move_id.state in ['assigned']:
                    #     move_id.sudo().write({
                    #         'quantity_done': move_id.forecast_availability,
                    #     })
                    for line in move_id.move_line_ids:
                        line.qty_done = move_id.product_uom_qty
                # using below code we will validate delivery order automatically
                picking_id.with_context(skip_sms=True).button_validate()
                return True, 'Delivery Order Validated Successfully', False, 'completed'
        except Exception as e:
            error_msg = 'Can not validate delivery order of sale order - {0} \n Error: {1}'.format(
                sale_order_id.name, e)
            return False, error_msg, True, 'partially_completed'

    def auto_create_woocommerce_invoice(self, sale_order_id, sale_auto_workflow_id):
        """
        Auto-create and validate the invoice for a WooCommerce Sale Order
        based on auto workflow configuration.
        Also auto-create payment entry if the order is already paid in WooCommerce.
        """

        try:
            # ✅ Step 1: Check if invoice creation is required
            if sale_order_id.invoice_status != "to invoice":
                return False, f"No items to invoice for {sale_order_id.name}", False, 'skipped'

            # ✅ Step 2: Ensure workflow journal exists
            journal = sale_auto_workflow_id.journal_id
            if not journal:
                return False, f"No journal configured in workflow for {sale_order_id.name}", True, 'failed'

            # ✅ Step 3: Create Invoice (draft)
            ctx = {"default_journal_id": journal.id}
            invoices = sale_order_id.with_context(ctx)._create_invoices()

            if not invoices:
                return False, f"Invoice not created for {sale_order_id.name}", True, 'failed'

            invoice = invoices[0]

            # ✅ Step 4: Validate (post) invoice
            invoice.action_post()

            # -------------------------------------------------------------------------
            # ✅ ✅ OPTIONAL STEP — Create Payment IF WooCommerce Order is Paid
            # -------------------------------------------------------------------------
            # You can store this boolean on the sale order when importing:
            # sale_order_id.woocommerce_is_paid = True/False
            # or lookup using wc order payload like:
            # if wc_status in ('processing','completed'): paid=True
            # -------------------------------------------------------------------------
            if sale_order_id.woocommerce_is_paid:  # <-- Your field flag
                payment_method_line = journal.inbound_payment_method_line_ids.filtered(
                    lambda x: x.name.lower() == 'manual payment'
                )

                if not payment_method_line:
                    return False, (
                            "Payment method line not found in journal '%s' → Cannot create payment for order %s"
                            % (journal.name, sale_order_id.name)
                    ), True, 'partially_completed'

                # ✅ Create Payment in Odoo
                payment_vals = {
                    'payment_type': 'inbound',
                    'partner_id': sale_order_id.partner_id.id,
                    'amount': invoice.amount_total,
                    'journal_id': journal.id,
                    'payment_method_line_id': payment_method_line.id,
                    'date': fields.Date.today(),
                    'ref': sale_order_id.woocommerce_order_id or sale_order_id.name,
                }
                payment = self.env['account.payment'].create(payment_vals)
                payment.action_post()

            # ✅ Completed Successfully
            return True, "Invoice created & validated successfully", False, 'completed'

        except Exception as e:
            error_msg = f"Cannot create invoice for Sale Order {sale_order_id.name}\nError: {e}"
            return False, error_msg, True, 'failed'

    def check_automatic_workflow_process_for_woocommerce_order(self, instance_id, woocommerce_order_dictionary,
                                                               sale_order_id, financial_status, skip_auto_workflow):
        result = False
        log_msg = ''
        fault_or_not = False
        line_state = ''
        sale_auto_workflow_id = financial_status.sale_auto_workflow_id
        if skip_auto_workflow:
            result = True
            log_msg = "Order Created Successfully without perform sale auto workflow"
            line_state = 'completed'
            return result, log_msg, fault_or_not, line_state
        # This code confirms a sale order if the "confirm sale order" field is true in the sales auto workflow.
        if sale_auto_workflow_id and sale_auto_workflow_id.confirm_sale_order:
            result, log_msg, fault_or_not, line_state = self.auto_confirm_woocommerce_sale_order(sale_order_id)

        # This code confirms a delivery order if the "confirm delivery order" field is true in the sales auto workflow.
        if (
                sale_auto_workflow_id and sale_auto_workflow_id.confirm_sale_order and sale_auto_workflow_id.validate_delivery_order and
                sale_order_id.state == 'sale'):
            result, log_msg, fault_or_not, line_state = self.auto_validate_woocommerce_delivery_order(sale_order_id)
            if not result:
                return result,log_msg,fault_or_not,line_state
        if (
                sale_auto_workflow_id
                and sale_auto_workflow_id.create_invoice
                and sale_order_id.state == 'sale'
        ):
            result, log_msg, fault_or_not, line_state = self.auto_create_woocommerce_invoice(sale_order_id)
        #  If no workflow actions were triggered, still mark process as successful (not failed)
        if not sale_auto_workflow_id or (
                not sale_auto_workflow_id.confirm_sale_order
                and not sale_auto_workflow_id.validate_delivery_order
        ):
            result = True
            log_msg = "Sale order created successfully (no automatic workflow applied)"
            fault_or_not = False
            line_state = 'completed'

        return result, log_msg, fault_or_not, line_state

    def process_import_order_from_woocommerce(self, woocommerce_order_dictionary, instance_id, log_id=False,
                                              line=False, cancelled = False):

        """This method was used for import the order from woocommerce to odoo and process that order
            @param : woocommerce_order_dictionary : json response of specific order queue line
                     instance_id : object of instance__id
                     log_id : object of created log_id when process was start
                     line : object of specific order queue line
            return : sale order :- Object of sale order which is created in odoo based on order queue line response data
        """
        # line.processed_at = fields.Datetime.now()
        woocommerce_taxes = {}
        order_number = str(woocommerce_order_dictionary.get("number") or "")
        existing_order = self.search([("instance_id", "=", instance_id.id),
                                      ("woocommerce_order_number", "=", order_number)], limit=1)
        if existing_order:
            line.sale_order_id = existing_order.id
            if cancelled:
                if existing_order.state not in ['cancel', 'done']:
                    existing_order.action_cancel()
                    msg = "Order Number {0} - Cancelled in Odoo (from WooCommerce)".format(existing_order.name)
                    return True, msg, False, 'completed'
                else:
                    msg = "Order Number {0} - Already Cancelled in Odoo".format(existing_order.name)
                    return True, msg, False, 'completed'
            else:
                msg = "Order Number {0} - Already Exists in Odoo.".format(existing_order.name)
                return True, msg, False, 'completed'
        if cancelled:
            msg = f"Order {woocommerce_order_dictionary.get('number')} not found in Odoo — cannot cancel."
            return False, msg, True, 'failed'

        success, financial_status, message, is_error, state = self.create_or_update_payment_gateway_and_workflow(
            woocommerce_order_dictionary, instance_id,
            line)
        if not success or not financial_status:
            return False, message, True, 'failed'
        customer_id = self.find_create_woocommerce_customer_in_odoo(instance_id, woocommerce_order_dictionary,
                                                                    log_id=False, line=False)
        if not customer_id:
            error_msg = 'Can not find customer details in sale order response {0}'.format(
                woocommerce_order_dictionary.get('name', ''))
            return False, error_msg, True, 'failed'

        # Here need to check missing value related code like check product available or not in odoo
        if instance_id.woocommerce_apply_tax_in_order == "create_woocommerce_tax":
            woocommerce_taxes = self.woocommerce_prepare_tax_data(woocommerce_order_dictionary, line, instance_id,
                                                                  woocommerce_taxes)
            if isinstance(woocommerce_taxes, bool):
                return False

        currency_id = self.env['res.currency'].search([('name', '=', woocommerce_order_dictionary.get('currency'))], limit=1)
        price_list_id = self.get_price_list(currency_id, instance_id)
        date_order = self.convert_woocommerce_order_date(woocommerce_order_dictionary)
        sale_order_id = self.create({"partner_id": customer_id and customer_id.id,
                                     "date_order": date_order,
                                     'company_id': instance_id.company_id.id or '',
                                     'warehouse_id': instance_id.warehouse_id.id or '',
                                     'pricelist_id': price_list_id.id,
                                     'state': 'draft',
                                     'name': woocommerce_order_dictionary.get('id', ''),
                                     'instance_id': instance_id.id,
                                     })
        payment_gateway_id = financial_status.payment_gateway_id.id if financial_status.payment_gateway_id else \
            False
        sale_order_id.update({'picking_policy': financial_status.sale_auto_workflow_id.policy_of_picking,
                              'payment_gateway_id': payment_gateway_id,
                              "note": woocommerce_order_dictionary.get("customer_note"),
                              'woocommerce_order_number': woocommerce_order_dictionary.get('number', ''),
                              'woocommerce_sale_auto_workflow_id': financial_status.sale_auto_workflow_id.id,
                              "woocommerce_order_id": woocommerce_order_dictionary.get("id"),
                              })

        line.sale_order_id = sale_order_id.id  # this line used for set the sale order id in order queue line sale order field
        tax_included = woocommerce_order_dictionary.get("prices_include_tax")
        if sale_order_id:
            order_lines, msg, fault_or_not, line_state, skip_auto_workflow = sale_order_id.create_woocommerce_sale_order_line(
                sale_order_id,
                woocommerce_order_dictionary,
                woocommerce_taxes,
                instance_id=instance_id,
                log_id=log_id,
                order_queue_line=line)
            if not order_lines:
                return False, msg, True, line_state
            sale_order_id.woocommerce_create_shipping_fee_coupon_lines(instance_id, woocommerce_order_dictionary,
                                                                       tax_included, woocommerce_taxes, sale_order_id)
            # if float(woocommerce_order_dictionary.get('discount_total', 0.0)) > 0.0:
            #     # Extract coupon code(s)
            #     coupon_lines = woocommerce_order_dictionary.get('coupon_lines', [])
            #     coupon_codes = []
            #     if coupon_lines:
            #         for coupon in coupon_lines:
            #             code = coupon.get('code')
            #             if code:
            #                 coupon_codes.append(code)
            #
            #     # Create a readable coupon name string
            #     coupon_name = ', '.join(coupon_codes) if coupon_codes else 'Discount'
            #
            #     # Prepare discount order line values
            #     order_line_vals = self.prepare_vals_for_sale_order_line(
            #         float(woocommerce_order_dictionary.get('discount_total')) * -1,
            #         1,
            #         instance_id.woocommerce_discount_product_id,
            #         sale_order_id
            #     )
            #
            #     # Update order line with additional info
            #     order_line_vals.update({
            #         # 'price_unit': float(woocommerce_order_dictionary.get('discount_total')) * -1,
            #         'name': f"Discount ({coupon_name})"
            #     })
            #
            #     # Create sale order line
            #     sale_order_line = self.env['sale.order.line'].create(order_line_vals)
            #     sale_order_line.with_context(round=False)._compute_amount()

            check_process_status, log_msg, fault_or_not, line_state = self.check_automatic_workflow_process_for_woocommerce_order(
                instance_id, woocommerce_order_dictionary, sale_order_id, financial_status, skip_auto_workflow)
            # if check_process_status:
            #     msg = "sale order created successfully" if not log_msg else log_msg
            #     return True, msg, False, 'completed'
            msg = "sale order created successfully" if not log_msg else log_msg
            return check_process_status, msg, fault_or_not, line_state
