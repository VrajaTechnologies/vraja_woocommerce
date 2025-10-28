from odoo import fields, models
import json

class ExportWoocommerceProduct(models.TransientModel):
    _name = "woocommerce.product.export"
    _description = "Woocommerce Product Export Wizard"

    set_price = fields.Boolean(string="Set Price")
    set_image = fields.Boolean(string="Set Image")

    def export_woocommerce_product(self):
        """this method is used for export product in woocommerce instance"""
        failed_product = []
        woocommerce_instance = self.env['woocommerce.product.listing'].browse(
            self.env.context.get("active_ids", [])).mapped('woocommerce_instance_id')[:1]
        active_product_ids = self.env.context.get("active_ids", [])
        product_template_ids = self.env['woocommerce.product.listing'].browse(active_product_ids)
        log_id = self.env['woocommerce.log'].generate_woocommerce_logs(
            "product", "export", woocommerce_instance, "Export Product Process Started"
        )
        for product_template_id in product_template_ids:
            if not product_template_id.exported_in_woocommerce:
                product_vals = {
                    "name": product_template_id.product_tmpl_id.name,
                    "sku": str(product_template_id.product_tmpl_id.default_code or ''),
                    "description": product_template_id.description or "",
                    "weight": str(product_template_id.product_tmpl_id.weight),
                    "regular_price": str(product_template_id.product_tmpl_id.standard_price)
                }
                if self.set_price and product_template_id.product_tmpl_id.list_price:
                    product_vals["price"] = str(product_template_id.product_tmpl_id.list_price)
                # if self.set_image and product_template_id.product_tmpl_id.image_1920:
                # product_vals["images"] = [{
                #     "src": f"data:image/png;base64,{product_template_id.product_tmpl_id.image_1920 or ''}"
                # }]
                if product_template_id.woocommerce_product_listing_items:
                    product_vals["type"] = "variable"
                    product_attributes = []
                    for attr_line in product_template_id.product_tmpl_id.attribute_line_ids:
                        product_attributes.append({
                            "name": str(attr_line.attribute_id.name),
                            "options": [val.name for val in attr_line.value_ids],
                            "variation": True,
                            "visible": True
                        })
                    product_vals["attributes"] = product_attributes
                product_vals_json = json.dumps(product_vals)
                try:
                    woocommerce_product_api = (
                        "{0}/wp-json/wc/v3/products".format(
                            woocommerce_instance.woocommerce_url
                        ))
                    params = "per_page=100"
                    response_status, response_data, next_page_link = woocommerce_instance.woocommerce_api_calling_process(
                        "POST",
                        woocommerce_product_api,
                        product_vals_json,
                        params)
                    if isinstance(response_data, str):
                        response_data = json.loads(response_data)
                    if response_status:
                        product_template_id.exported_in_woocommerce = True
                        result = response_data
                        product_id = result.get('id')
                        product_template_id.write({
                            'woocommerce_product_id': product_id,
                        })
                        message = f"Product '{product_template_id.name}' exported successfully (WooCommerce ID: {result.get('id')})."
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                           woocommerce_instance,
                                                                                           message, False, message,
                                                                                           log_id, False)
                    else:
                        error_message = f"Failed to export '{product_template_id.name}': {response_data}"
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                           woocommerce_instance,
                                                                                           error_message, False,
                                                                                           error_message, log_id,
                                                                                           True)
                except Exception as e:
                    failed_product.append(product_template_id.id)
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                        'product', 'export', woocommerce_instance,
                        f"Failed to export product {product_template_id.name}: {e}",
                        False, f"Failed to export product {product_template_id.name}", log_id, True
                    )
                product_variants = product_template_id.woocommerce_product_listing_items
                for product_variant in product_variants:
                    product_variant_odoo = product_variant.product_id
                    attributes = [{
                        "name": val.attribute_id.name,
                        "option": val.name
                    }
                        for val in product_variant_odoo.product_template_variant_value_ids
                    ]
                    product_variant_vals = {
                        "name": product_variant.name,
                        "sku": str(product_variant.product_sku),
                        "description": product_variant.product_id.description or "",
                        "weight": str(product_variant.product_id.weight),
                        "regular_price": str(product_variant.product_id.standard_price),
                        "attributes": attributes
                    }
                    if self.set_price and product_variant.product_id.list_price:
                        product_variant_vals['price'] = str(product_variant.product_id.list_price)
                    # if self.set_image and product_variant.product_id.image_1920:
                    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                    #     product_variant_vals["image"] = {
                    #         "src": f"{base_url}/web/image/product.product/{product_variant.product_id.id}/image_1920"
                    #     }
                    product_var_json = json.dumps(product_variant_vals)
                    try:
                        woocommerce_product_variant_api = (
                            "{0}/wp-json/wc/v3/products/{1}/variations".format(
                                woocommerce_instance.woocommerce_url,
                                product_template_id.woocommerce_product_id,
                            ))
                        response_status, response_data, next_page_link = woocommerce_instance.woocommerce_api_calling_process(
                            "POST",
                            woocommerce_product_variant_api,
                            product_var_json,
                            None)
                        if isinstance(response_data, str):
                            response_data = json.loads(response_data)
                        if response_status:
                            result = response_data
                            product_variant.write({
                                'woocommerce_product_variant_id': result.get('id')
                            })
                            message = f"Product: '{product_variant.name}' exported successfully (WooCommerce ID: {result.get('id')})."
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               message, False,
                                                                                               message, log_id,
                                                                                               False)
                        else:
                            error_message = f"Failed to export '{product_variant.name}': {response_data}"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               error_message, False,
                                                                                               error_message,
                                                                                               log_id,
                                                                                               True)
                    except Exception as e:
                        failed_product.append(product_variant.id)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'export', woocommerce_instance,
                            f"Failed to export product {product_template_id.name}: {e}",
                            False, f"Failed to export product {product_template_id.name}", log_id, True
                        )
            else:
                message = "Invalid Product. {0} Already exist in woocommerce".format(product_template_id.name)
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                   woocommerce_instance,
                                                                                   message, False, message, log_id,
                                                                                   True)
