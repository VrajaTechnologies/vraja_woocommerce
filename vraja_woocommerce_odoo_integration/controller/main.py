import base64
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger("Woocommerce Controller")


class MarketplaceProductImage(http.Controller):

    @http.route("/woocommerce/product/image/<string:encodedimage>", type='http', auth='public')
    def retrive_woocommerce_product_image_from_url(self, encodedimage=''):
        if encodedimage:
            try:
                decode_data = base64.urlsafe_b64decode(encodedimage)
                res_id = str(decode_data, "utf-8")
                status, headers, content = request.env['ir.http'].sudo().binary_content(
                    model='woocommerce.product.image', id=res_id,
                    field='image')
                content_base64 = base64.b64decode(content) if content else ''
                headers.append(('Content-Length', len(content_base64)))
                return request.make_response(content_base64, headers)
            except Exception:
                return request.not_found()
        return request.not_found()

class Main(http.Controller):

    @http.route(['/woocommerce/webhook_for_customer_create'], csrf=False, auth="public", type="json")
    def customer_create_webhook(self):
        """
        Route for handling customer create webhook for Woocommerce. This route calls while new customer create
        in the Woocommerce store.
        """
        _logger.info("Creating Customer at webhook...")
        webhook_route = request.httprequest.path.split('/')[1]
        _logger.info("webhook route: %s", webhook_route)
        res, instance = self.get_basic_info(webhook_route)
        if not res:
            _logger.info("returning...res not Found res in response")
            return
        if res.get("first_name") and res.get("last_name"):
            _logger.info("%s call for Customer: %s", webhook_route,
                         (res.get("first_name") + " " + res.get("last_name")))
            self.customer_webhook_process(instance, res)
        return

    def customer_webhook_process(self, instance_id, res):
        """
        This method used for call child method of customer create process.
        """
        _logger.info("Woocommerce Customer response : {}".format(res))
        queue_id = request.env['customer.data.queue'].sudo().generate_woocommerce_customer_queue(instance_id)
        request.env['customer.data.queue.line'].sudo().create_woocommerce_customer_queue_line(res, instance_id,
                                                                                          queue_id)
        queue_id.sudo().process_woocommerce_customer_queue()

    def get_basic_info(self, route):
        """
        This method is used to check that instance and webhook are active or not. If yes then return response and
        instance, If no then return response as False and instance.
        """
        _logger.info("Getting basic info...")
        res = request.get_json_data()
        _logger.info("Get json data : ", res)
        host = request.httprequest.headers.get("X-woocommerce-Shop-Domain")
        _logger.info("host: %s", host)
        instance = request.env["woocommerce.instance.integration"].sudo().with_context(active_test=False).search(
            [("woocommerce_url", "ilike", host)], limit=1)
        _logger.info("Instance Data: %s", instance)
        webhook = request.env["woocommerce.webhook"].sudo().search([("delivery_url", "ilike", route),
                                                                ("instance_id", "=", instance.id)], limit=1)
        _logger.info("webhook data: %s", webhook)
        if not instance.active or not webhook.state == "active":
            _logger.info("The method is skipped. It appears the instance:%s is not active or that "
                         "the webhook %s is not active.", instance.name, webhook.webhook_name)
            res = False
        return res, instance
