# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import json
import logging
import requests

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger("WooCommerce")


class AccountMove(models.Model):
    _inherit = "account.move"

    woocommerce_refund_id = fields.Char("WooCommerce Refund ID")
    woocommerce_instance_id = fields.Many2one("woocommerce.instance.integration", "WooCommerce Instance")
    is_refunded_in_woocommerce = fields.Boolean("Refunded In Woo Commerce", default=False)

    def refund_in_woocommerce(self):
        for refund in self:

            # Must be a credit note
            if refund.move_type != "out_refund":
                raise UserError(_("Refund can only be processed for Credit Notes."))

            # Must have Woo Instance
            if not refund.woocommerce_instance_id:
                raise UserError(_("WooCommerce Instance not set on this Credit Note."))

            instance = refund.woocommerce_instance_id

            # Do not allow double refund
            if refund.is_refunded_in_woocommerce:
                raise UserError(_("Refund already synced to WooCommerce."))

            # Detect Woo Order
            orders = refund.invoice_line_ids.sale_line_ids.order_id.filtered(
                lambda o: o.woocommerce_order_id
            )
            if not orders:
                raise UserError(_("No related WooCommerce order found for this refund."))

            if len(orders) > 1:
                raise UserError(_(
                    "This credit note belongs to multiple Woo orders.\n"
                    "Please split the credit note and refund individually."
                ))

            order = orders[0]

            # Woo requires positive amount
            amount = abs(refund.amount_total)

            payload = {
                "amount": str(amount),
                "reason": refund.ref or refund.name or "Refund created in Odoo",
                "api_refund": False,
            }

            # Build API URL
            refund_url = f"{instance.woocommerce_url}/wp-json/wc/v3/orders/{order.woocommerce_order_id}/refunds"

            # Call WooCommerce API (using your common method)
            response_status, response_data, next_page_link = instance.woocommerce_api_calling_process(
                "POST", refund_url, json.dumps(payload), False
            )

            if not response_status:
                raise UserError(_("WooCommerce Refund Failed:\n%s") % response_data.text)

            # Save refund ID if WooCommerce gives one
            refund.woocommerce_refund_id = response_data.get("id")

            refund.is_refunded_in_woocommerce = True

        return True
