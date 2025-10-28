from odoo import fields, models
import json

class UpdateWoocommerceProduct(models.TransientModel):
    _name = "woocommerce.product.update"
    _description = "Woocommerce Product Update Wizard"

    set_price = fields.Boolean(string="Set Price", help="To update price select Set Price")
    set_image = fields.Boolean(string="Set Image", help="To update image select Set Image")

    def update_woocommerce_product(self):
        """This method is used for update product from woocommerce instance"""
        failed_product = []
        woocommerce_instance = self.env['woocommerce.product.listing'].browse(
            self.env.context.get("active_ids", [])).mapped('woocommerce_instance_id')[:1]
        active_product_ids = self.env.context.get("active_ids", [])
        product_template_ids = self.env['woocommerce.product.listing'].browse(active_product_ids)
        log_id = self.env['woocommerce.log'].generate_woocommerce_logs(
            "product", "update", woocommerce_instance, "Update Product Process Started"
        )
        for product_template_id in product_template_ids:
            if product_template_id.woocommerce_product_id:
                if product_template_id.exported_in_woocommerce:
                    product_vals = {
                        "name": product_template_id.product_tmpl_id.name,
                        "sku": str(product_template_id.product_tmpl_id.default_code or ''),
                        "description": product_template_id.description or "",
                        "weight": str(product_template_id.product_tmpl_id.weight),
                        "regular_price": str(product_template_id.product_tmpl_id.standard_price)  # cost
                    }
                    if self.set_price and product_template_id.product_tmpl_id.list_price:
                        product_vals["price"] = str(product_template_id.product_tmpl_id.list_price)
                    # if self.set_image and product_variant.product_id.image_1920:
                    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    #     product_variant_vals["image"] = {
                    #         "src": f"{base_url}/web/image/product.product/{product_variant.product_id.id}/image_1920"
                    #     }
                    product_vals_json = json.dumps(product_vals)
                    try:
                        woocommerce_product_api = (
                            "{0}/wp-json/wc/v3/products/{1}".format(
                                woocommerce_instance.woocommerce_url,
                                product_template_id.woocommerce_product_id
                            ))
                        params = "per_page=100"
                        response_status, response_data, next_page_link = woocommerce_instance.woocommerce_api_calling_process(
                            "PUT",
                            woocommerce_product_api,
                            product_vals_json,
                            params)
                        if isinstance(response_data, str):
                            response_data = json.loads(response_data)
                        if response_status:
                            result = response_data
                            message = f"Product '{product_template_id.name}' updated successfully (WooCommerce ID: {result.get('id')})."
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                               woocommerce_instance,
                                                                                               message, False, message,
                                                                                               log_id, False)
                        else:
                            error_message = f"Failed to update '{product_template_id.name}': {response_data}"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                               woocommerce_instance,
                                                                                               error_message, False,
                                                                                               error_message, log_id,
                                                                                               True)
                    except Exception as e:
                        failed_product.append(product_template_id.id)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'update', woocommerce_instance,
                            f"Failed to update product {product_template_id.name}: {e}",
                            False, f"Failed to update product {product_template_id.name}", log_id, True
                        )
                product_variants = product_template_id.woocommerce_product_listing_items
                for product_variant in product_variants:
                    product_variant_vals = {
                        "name": product_variant.name,
                        "sku": product_variant.product_sku,
                        "description": product_variant.product_id.description or "",
                        "weight": str(product_variant.product_id.weight),
                        "regular_price": str(product_variant.product_id.standard_price)
                    }
                    if self.set_price and product_variant.product_id.list_price:
                        product_variant_vals['price'] = str(product_variant.product_id.list_price)
                    if self.set_image and product_variant.product_id.image_1920:
                        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                        product_variant_vals["image"] = {
                            "src": f"{base_url}/web/image/product.product/{product_variant.product_id.id}/image_1920"
                        }
                    product_var_json = json.dumps(product_variant_vals)
                    try:
                        woocommerce_product_variant_api = (
                            "{0}/wp-json/wc/v3/products/{1}/variations/{2}".format(
                                woocommerce_instance.woocommerce_url,
                                product_template_id.woocommerce_product_id,
                                product_variant.woocommerce_product_variant_id
                            ))
                        response_status, response_data, next_page_link = woocommerce_instance.woocommerce_api_calling_process(
                            "PUT",
                            woocommerce_product_variant_api,
                            product_var_json,
                            None)
                        if isinstance(response_data, str):
                            response_data = json.loads(response_data)
                        if response_status:
                            result = response_data

                            message = f"Product: '{product_variant.name}' updated successfully (WooCommerce ID: {result.get('id')})."
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                               woocommerce_instance,
                                                                                               message, False,
                                                                                               message, log_id,
                                                                                               False)
                        else:
                            error_message = f"Failed to update '{product_variant.name}': {response_data}"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                               woocommerce_instance,
                                                                                               error_message, False,
                                                                                               error_message,
                                                                                               log_id,
                                                                                               True)
                    except Exception as e:
                        failed_product.append(product_variant.id)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'update', woocommerce_instance,
                            f"Failed to update product {product_template_id.name}: {e}",
                            False, f"Failed to update product {product_template_id.name}", log_id, True
                        )
            else:
                message = "Invalid Product. {0} Not exist in woocommerce".format(product_template_id.name)
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                   woocommerce_instance,
                                                                                   message, False, message, log_id,
                                                                                   True)
