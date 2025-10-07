import base64
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger("Woocommerce Controller")


class MarketplaceProductImage(http.Controller):

    @http.route(['/woocommerce/product/image/<string:encodedimage>'], type='http', auth='public')
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