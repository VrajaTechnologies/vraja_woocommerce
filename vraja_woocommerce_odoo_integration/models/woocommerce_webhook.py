import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

_logger = logging.getLogger("Woocommerce Webhook")


class WoocommerceWebhook(models.Model):
    _name = "woocommerce.webhook"
    _description = 'Woocommerce Webhook'

    webhook_name = fields.Char(string='Name')
    state = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')], default='inactive')
    webhook_id = fields.Char('Webhook Id in Woocommerce')
    delivery_url = fields.Text("Delivery URL")
    webhook_action = fields.Selection([('customer.created', 'Upon the creation of a customer.'),
                                       ('order.created', 'When Order is Created'),
                                       ('product.created', 'When product is created.')])
    instance_id = fields.Many2one("woocommerce.instance.integration",
                                  string="This Woocommerce instance has generated a Webhook.",
                                  ondelete="cascade")

    @api.model_create_multi
    def create(self, values):
        """
        This method is used to create a webhook.
        """
        for val in values:
            available_webhook = self.search(
                [('instance_id', '=', val.get('instance_id')), ('webhook_action', '=', val.get('webhook_action'))],
                limit=1)
            if available_webhook:
                raise UserError(_('Webhook is already created with the same ID.'))

            result = super(WoocommerceWebhook, self).create(val)
            result.get_webhook()
            _logger.info("CREATE WEBHOOK : %s", result)
        return result

    def get_webhook(self):
        """
        Creates webhook in woocommerce Store for webhook in Odoo if no webhook is
        there, otherwise updates status of the webhook, if it exists in woocommerce store.
        """
        instance_obj = self.instance_id
        if not instance_obj or instance_obj._name == '_unknown':
            raise UserError(_("WooCommerce instance is not defined for this webhook."))
        route = self.get_route()
        current_url = instance_obj.get_base_url()
        url = current_url + route
        _logger.info("Webhook URL : %s", url)
        # if url[:url.find(":")] == 'http':
        #     raise UserError(_("Address protocol http:// is not supported for creating the webhooks."))

        webhook_vals = {
            "name": self.webhook_name,
            "topic": self.webhook_action,
            "delivery_url": url,
            "format": "json",
            "status": self.state
            }
        webhook_json = json.dumps(webhook_vals)
        woocommerce_webhook_api = (
            "{0}/wp-json/wc/v3/webhooks".format(
                instance_obj.woocommerce_url
            ))
        params = "per_page=100"
        response_status, response_data, next_page_link = instance_obj.woocommerce_api_calling_process(
            "POST",
            woocommerce_webhook_api,
            webhook_json,
            params)
        _logger.info("Creates webhook in Woocommerce Store : %s", response_data)
        if response_status and isinstance(response_data, dict):
            webhook_id = response_data.get("id")
            if webhook_id:
                self.write({
                    "webhook_id": webhook_id,
                    "delivery_url": url,
                    "state": "active"
                })
        else:
            raise UserError(_("Failed to create webhook on WooCommerce."))
        return True

    def get_route(self):
        """
        Gives delivery URL for the webhook as per the Webhook Action.
        """
        webhook_action = self.webhook_action
        if webhook_action == 'customer.created':
            route = "/woocommerce/webhook/customer_create"
        elif webhook_action == 'order.created':
            route = "/woocommerce/webhook/orders_create"
        elif webhook_action == 'product.created':
            route = "/woocommerce/webhook/products_create"
        return route
