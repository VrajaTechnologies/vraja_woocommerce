import json
from odoo import fields, models
from odoo.exceptions import UserError, ValidationError

class PrepareProductForExportWoocommerceInstance(models.TransientModel):
    _name = "prepare.product.for.export.woocommerce.instance"
    _description = "Export Product in Woocommerce Wizard"

    set_price = fields.Boolean(string="Set Price")
    set_image = fields.Boolean(string="Set Image")
    woocommerce_instance_id = fields.Many2one('woocommerce.instance.integration', string="Woocommerce Instance")

    def prepare_product_for_export_woocommerce_instance(self):
        """export and update product in woocommerce"""
        error_messages = []
        no_sku_products = []
        no_sku_product_variant = []
        woocommerce_instance = self.woocommerce_instance_id
        log_id = self.env['woocommerce.log'].generate_woocommerce_logs("product", "export", woocommerce_instance,
                                                                       "Product Export Process Started")
        active_template_ids = self.env.context.get("active_ids", [])
        product_template_ids = self.env['product.template'].browse(active_template_ids)
        product_templates = product_template_ids.filtered(lambda template: template.detailed_type == "product")
        non_storable_products =product_template_ids.filtered(lambda template: template.detailed_type != "product")
        woocommerce_products = self.env['woocommerce.product.listing']
        woocommerce_product_variants = self.env['woocommerce.product.listing.item']

        for product in product_templates:
            if not product.default_code:
                variants = product.product_variant_ids
                variants_with_sku = variants.filtered(lambda v: v.default_code)
                if not variants_with_sku:
                    product_name = product.name
                    no_sku_products.append(product_name)
                    message = f"Product '{product.name}' variants have no SKU so product can not exported. (Product ID: {product.id})."
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                       woocommerce_instance,
                                                                                       message, False, message,
                                                                                       log_id, False)
                    continue
            if not product.default_code and not product.attribute_line_ids:
                product_name = product.name
                no_sku_products.append(product_name)
                message = f"Product '{product.name}' can not be exported without SKU (Product ID: {product.id})."
                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                   woocommerce_instance,
                                                                                   message, False, message,
                                                                                   log_id, False)
                continue
            woocommerce_product = self.env['woocommerce.product.listing'].search([
                ('product_tmpl_id', '=', product.id),
                ('woocommerce_instance_id', '=', woocommerce_instance.id)
            ], limit=1)
            if woocommerce_product:
                try:
                    product_data = {
                        "name": product.name,
                        "product_tmpl_id": product.id,
                        "woocommerce_default_code": product.default_code,
                        "product_catg_id": product.categ_id.id,
                        "description": product.description or "",
                    }
                    woocommerce_product.write(product_data)
                    message = f"Product '{product.name}' Updated successfully (Product ID: {product.id})."
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                       woocommerce_instance,
                                                                                       message, False, message,
                                                                                       log_id, False)
                except Exception as e:
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                        'product', 'update', woocommerce_instance,
                        f"Failed to update product {product.name}: {e}",
                        False, f"Failed to update product {product.name}", log_id, True
                    )

                product_variants = product.product_variant_ids
                existing_wc_variants = self.env['woocommerce.product.listing.item'].search([
                    ('woocommerce_product_listing_id', '=', woocommerce_product.id)
                ])
                variants_to_remove = existing_wc_variants.filtered(
                    lambda v: v.product_id not in product_variants
                )
                if variants_to_remove:
                    try:
                        variant_names = ', '.join(variants_to_remove.mapped('name'))
                        variants_to_remove.unlink()
                        message = f"Removed old variants: {variant_names} from product '{woocommerce_product.name}'"
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'export', woocommerce_instance,
                            message, False, message, log_id, False
                        )
                    except Exception as e:
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'export', woocommerce_instance,
                            f"Failed to delete old variants for '{woocommerce_product.name}': {e}",
                            False, f"Failed to delete variants for '{woocommerce_product.name}'",
                            log_id, True
                        )
                if product.attribute_line_ids and product_variants:
                    for product_variant in product_variants:
                        variant_name = ', '.join(product_variant.product_template_variant_value_ids.mapped('name'))
                        if not product_variant.default_code:
                            no_sku_product_variant.append(variant_name)
                            message = f"Product '{product_variant.product_name}' can not be exported without SKU (Product variant ID: {product_variant.id})."
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               message, False, message,
                                                                                               log_id, False)
                            continue
                        woocommerce_product_variant = self.env['woocommerce.product.listing.item'].search(
                            [('product_sku', '=', product_variant.default_code)], limit=1)
                        if not woocommerce_product_variant:
                            woocommerce_product_variant = self.env['woocommerce.product.listing.item'].search(
                                [('product_id', '=', product_variant.id)], limit=1)
                        if woocommerce_product_variant:
                            try:
                                product_variant_data = {
                                    "name": ', '.join(
                                        product_variant.product_template_variant_value_ids.mapped('name')),
                                    "product_id": product_variant.id,
                                    "product_sku": product_variant.default_code,
                                }
                                woocommerce_product_variant.write(product_variant_data)
                                message = f"Product Variant '{product_variant.id}' Updated successfully (product variant ID: {woocommerce_product_variant.id})."
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'update',
                                                                                                   woocommerce_instance,
                                                                                                   message,
                                                                                                   False, message,
                                                                                                   log_id, False)
                            except Exception as e:
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                    'product', 'update', woocommerce_instance,
                                    f"Failed to update product {product.name}: {e}",
                                    False, f"Failed to update product {product.name}", log_id, True
                                )
                        else:
                            try:
                                wc_product_variant = {
                                    "name": ', '.join(
                                        product_variant.product_template_variant_value_ids.mapped('name')),
                                    'product_sku': product_variant.default_code,
                                    'product_id': product_variant.id,
                                    'woocommerce_product_listing_id': woocommerce_product.id,
                                    'woocommerce_instance_id': woocommerce_instance.id
                                }
                                new_variant = woocommerce_product_variants.create(wc_product_variant)
                                message = f"Product Variant {new_variant.name} Exported successfully (Product ID: {new_variant.id})."
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                                   woocommerce_instance,
                                                                                                   message,
                                                                                                   False, message,
                                                                                                   log_id, False)
                            except Exception as e:
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                    'product', 'export', woocommerce_instance,
                                    f"Failed to export product {product.name}: {e}",
                                    False, f"Failed to export product {product.name}", log_id, True
                                )
            else:
                try:
                    wc_product = {
                        'woocommerce_instance_id': self.woocommerce_instance_id.id,
                        'woocommerce_default_code': product.default_code,
                        'product_tmpl_id': product.id,
                        'name': product.name,
                        'product_catg_id': product.categ_id.id,
                        'description': product.description_sale or '',
                        'exported_in_woocommerce': False,
                        'woocommerce_product_id': False,
                    }
                    woocommerce_product_record = woocommerce_products.create(wc_product)
                    message = f"Product '{product.name}' Exported successfully (Product ID: {product.id})."
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                       woocommerce_instance,
                                                                                       message, False, message,
                                                                                       log_id, False)
                except Exception as e:
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                        'product', 'export', woocommerce_instance,
                        f"Failed to export product {product.name}: {e}",
                        False, f"Failed to export product {product.name}", log_id, True
                    )
                product_variants = product.product_variant_ids
                if product.attribute_line_ids and product_variants:
                    for product_variant in product_variants:
                        if not product_variant.default_code:
                            variant_name = ', '.join(product_variant.product_template_variant_value_ids.mapped('name'))
                            no_sku_product_variant.append(variant_name)
                            message = f"Product variant '{product_variant.product_name}' can not be exported without SKU (Product variant ID: {product_variant.id})."
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               message, False, message,
                                                                                               log_id, False)
                            continue
                        try:
                            wc_product_variant = {
                                "name": ', '.join(product_variant.product_template_variant_value_ids.mapped('name')),
                                'product_sku': product_variant.default_code,
                                'product_id': product_variant.id,
                                'woocommerce_product_listing_id': woocommerce_product_record.id,
                                'woocommerce_instance_id': woocommerce_instance.id
                            }
                            woocommerce_product_variants.create(wc_product_variant)

                            message = f"Product Variant {product_variant.id.name} Exported successfully (Product ID: {product_variant.id})."
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               message,
                                                                                               False, message,
                                                                                               log_id, False)
                        except Exception as e:
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                'product', 'export', woocommerce_instance,
                                f"Failed to export variant {product_variant.name} of {product.name}: {e}",
                                False, f"Failed to export variant {product_variant.name} of {product.name}: {e}",
                                log_id, True
                            )
            woocommerce_product_ids = woocommerce_products.search(
                [("product_tmpl_id", "=", product.id)])
            for woocommerce_product_id in woocommerce_product_ids:
                if not woocommerce_product_id.exported_in_woocommerce:
                    product_vals = {
                        "name": woocommerce_product_id.product_tmpl_id.name,
                        "sku": str(woocommerce_product_id.product_tmpl_id.default_code or ''),
                        "description": woocommerce_product_id.description or "",
                        "weight": str(woocommerce_product_id.product_tmpl_id.weight or "0.0"),
                        "regular_price": str(woocommerce_product_id.product_tmpl_id.standard_price)
                    }
                    if self.set_price and woocommerce_product_id.product_tmpl_id.list_price:
                        product_vals["price"] = str(woocommerce_product_id.product_tmpl_id.list_price)
                    # if self.set_image and woocommerce_product_id.product_tmpl_id.image_1920:
                    # product_vals["images"] = [{
                    #     "src": f"data:image/png;base64,{woocommerce_product_id.product_tmpl_id.image_1920 or ''}"
                    # }]
                    if woocommerce_product_id.woocommerce_product_listing_items:
                        product_vals["type"] = "variable"
                        product_attributes = []
                        for attr_line in woocommerce_product_id.product_tmpl_id.attribute_line_ids:
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
                            if not response_data.strip():
                                raise UserError("WooCommerce returned an empty response (server timeout or crash).")
                            if response_data.strip().startswith('<'):
                                raise UserError(f"WooCommerce returned HTML error page: {response_data[:300]}")
                            response_data = json.loads(response_data)
                        if response_status:
                            woocommerce_product_id.exported_in_woocommerce = True
                            result = response_data
                            product_id = result.get('id')
                            woocommerce_product_id.write({
                                'woocommerce_product_id': product_id,
                            })
                            message = f"Product '{woocommerce_product_id.name}' exported successfully in Woocommerce.(WooCommerce ID: {result.get('id')})"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               message, False, message,
                                                                                               log_id, False)
                        else:
                            error_message = f"Failed to export '{woocommerce_product_id.name}': {response_data} in Woocommerce"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export',
                                                                                               woocommerce_instance,
                                                                                               error_message, False,
                                                                                               error_message, log_id,
                                                                                               True)
                    except Exception as e:
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'export', woocommerce_instance,
                            f"Failed to export product in Woocommerce {woocommerce_product_id.name}: {e}",
                            False, f"Failed to export product {woocommerce_product_id.name} in Woocommerce", log_id,
                            True
                        )
                    if woocommerce_product_id.woocommerce_product_listing_items:
                        for product_var_id in woocommerce_product_id.woocommerce_product_listing_items:
                            attributes = [{
                                "name": val.attribute_id.name,
                                "option": val.name
                            }
                                for val in product_var_id.product_id.product_template_variant_value_ids
                            ]
                            product_variant_vals = {
                                "name": product_var_id.name,
                                "sku": str(product_var_id.product_sku),
                                "description": product_var_id.product_id.description or "",
                                "weight": str(product_var_id.product_id.weight),
                                "regular_price": str(product_var_id.product_id.standard_price),
                                "attributes": attributes
                            }
                            if self.set_price and product_var_id.product_id.list_price:
                                product_variant_vals['price'] = str(product_var_id.product_id.list_price)
                            # if self.set_image and product_var_id.product_id.image_1920:
                            #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                            #     product_variant_vals["image"] = {
                            #         "src": f"{base_url}/web/image/product.product/{product_var_id.product_id.id}/image_1920"
                            #     }
                            product_var_json = json.dumps(product_variant_vals)
                            try:
                                woocommerce_product_variant_api = (
                                    "{0}/wp-json/wc/v3/products/{1}/variations".format(
                                        woocommerce_instance.woocommerce_url,
                                        woocommerce_product_id.woocommerce_product_id,
                                    ))
                                response_status, response_data, next_page_link = woocommerce_instance.woocommerce_api_calling_process(
                                    "POST",
                                    woocommerce_product_variant_api,
                                    product_var_json,
                                    None)
                                if isinstance(response_data, str):
                                    if not response_data.strip():
                                        raise UserError(
                                            "WooCommerce returned an empty response (server timeout or crash).")
                                    if response_data.strip().startswith('<'):
                                        raise UserError(f"WooCommerce returned HTML error page: {response_data[:300]}")
                                    response_data = json.loads(response_data)

                                if response_status:
                                    result = response_data
                                    product_var_id.write({
                                        'woocommerce_product_variant_id': result.get('id')
                                    })
                                    message = f"Product variant '{product_var_id.name}' exported successfully  in Woocommerce.(WooCommerce ID: {result.get('id')})"
                                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('product',
                                                                                                       'export',
                                                                                                       woocommerce_instance,
                                                                                                       message, False,
                                                                                                       message, log_id,
                                                                                                       False)
                                else:
                                    error_message = f"Failed to export '{product_var_id.name}': {response_data} in Woocommerce"
                                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('product',
                                                                                                       'export',
                                                                                                       woocommerce_instance,
                                                                                                       error_message,
                                                                                                       False,
                                                                                                       error_message,
                                                                                                       log_id,
                                                                                                       True)
                            except Exception as e:
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                    'product', 'export', woocommerce_instance,
                                    f"Failed to export product in Woocommerce {woocommerce_product_id.name}: {e}",
                                    False, f"Failed to export product {woocommerce_product_id.name} in Woocommerce",
                                    log_id, True
                                )
                else:
                    try:
                        product_vals = {
                            "name": woocommerce_product_id.product_tmpl_id.name,
                            "description": woocommerce_product_id.description or "",
                            "weight": str(woocommerce_product_id.product_tmpl_id.weight or "0.0"),
                            "sku": str(woocommerce_product_id.product_tmpl_id.default_code or ""),
                            "regular_price": str(
                                woocommerce_product_id.product_tmpl_id.standard_price or "0.0"),
                        }
                        if self.set_price and woocommerce_product_id.product_tmpl_id.list_price:
                            product_vals["price"] = str(woocommerce_product_id.product_tmpl_id.list_price)

                        if woocommerce_product_id.product_tmpl_id.attribute_line_ids:
                            product_vals["type"] = "variable"
                            product_attributes = []
                            for attr_line in woocommerce_product_id.product_tmpl_id.attribute_line_ids:
                                product_attributes.append({
                                    "name": str(attr_line.attribute_id.name),
                                    "options": [val.name for val in attr_line.value_ids],
                                    "variation": True,
                                    "visible": True
                                })
                            product_vals["attributes"] = product_attributes
                        else:
                            product_vals["type"] = "simple"
                        product_vals_json = json.dumps(product_vals)

                        woocommerce_product_api = "{0}/wp-json/wc/v3/products/{1}".format(
                            woocommerce_instance.woocommerce_url,
                            woocommerce_product_id.woocommerce_product_id
                        )
                        response_status, response_data, _ = woocommerce_instance.woocommerce_api_calling_process(
                            "POST",
                            woocommerce_product_api,
                            product_vals_json,
                            None
                        )
                        if isinstance(response_data, str):
                            if not response_data.strip():
                                raise UserError("WooCommerce returned an empty response (server timeout or crash).")
                            if response_data.strip().startswith('<'):
                                raise UserError(f"WooCommerce returned HTML error page: {response_data[:300]}")
                            response_data = json.loads(response_data)

                        if response_status:
                            message = f"Product '{woocommerce_product_id.name}' updated successfully (WooCommerce ID: {response_data.get('id')})"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                'product', 'update', woocommerce_instance, message, False, message, log_id,
                                False
                            )
                        else:
                            error_message = f"Failed to update  product '{woocommerce_product_id.name}': {response_data}"
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                'product', 'update', woocommerce_instance, error_message, False, error_message,
                                log_id, True
                            )
                    except Exception as e:
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'product', 'update', woocommerce_instance,
                            f"Exception while updating  product '{woocommerce_product_id.name}': {e}",
                            False, f"Exception while updating  product '{woocommerce_product_id.name}'",
                            log_id, True
                        )
                    for product_variant in woocommerce_product_id.woocommerce_product_listing_items:
                        try:
                            variant_vals = {
                                "name": product_variant.name,
                                "sku": str(product_variant.product_sku),
                                "description": product_variant.product_id.description or "",
                                "weight": str(product_variant.product_id.weight or "0.0"),
                                "regular_price": str(product_variant.product_id.standard_price or "0.0"),
                            }
                            if self.set_price and product_variant.product_id.list_price:
                                variant_vals['price'] = str(product_variant.product_id.list_price)

                            attributes = [{
                                "name": val.attribute_id.name,
                                "option": val.name
                            } for val in product_variant.product_id.product_template_variant_value_ids]
                            if attributes:
                                variant_vals["attributes"] = attributes

                            product_var_json = json.dumps(variant_vals)

                            if product_variant.woocommerce_product_variant_id:
                                woocommerce_product_variant_api = (
                                    "{0}/wp-json/wc/v3/products/{1}/variations/{2}".format(
                                        woocommerce_instance.woocommerce_url,
                                        woocommerce_product_id.woocommerce_product_id,
                                        product_variant.woocommerce_product_variant_id
                                    ))
                            else:
                                woocommerce_product_variant_api = (
                                    "{0}/wp-json/wc/v3/products/{1}/variations".format(
                                        woocommerce_instance.woocommerce_url,
                                        woocommerce_product_id.woocommerce_product_id
                                    ))

                            response_status, response_data, _ = woocommerce_instance.woocommerce_api_calling_process(
                                "POST", woocommerce_product_variant_api, product_var_json, None
                            )
                            if isinstance(response_data, str):
                                if not response_data.strip():
                                    raise UserError(
                                        "WooCommerce returned an empty response (server timeout or crash).")
                                if response_data.strip().startswith('<'):
                                    raise UserError(f"WooCommerce returned HTML error page: {response_data[:300]}")
                                response_data = json.loads(response_data)

                            if response_status:
                                if not product_variant.woocommerce_product_variant_id:
                                    product_variant.write(
                                        {'woocommerce_product_variant_id': response_data.get('id')})

                                message = f"Product Variant '{product_variant.name}' updated successfully (WooCommerce ID: {response_data.get('id')})"
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                    'product', 'update', woocommerce_instance, message, False, message, log_id,
                                    False
                                )
                            else:
                                error_message = f"Failed to update variant '{product_variant.name}. Woocommerce Product ID: {woocommerce_product_id}': {response_data}"
                                self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                    'product', 'update', woocommerce_instance, error_message, False,
                                    error_message, log_id, True
                                )
                        except Exception as e:
                            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                                'product', 'update', woocommerce_instance,
                                f"Exception while updating variant '{product_variant.name}': {e}",
                                False, f"Exception while updating variant '{product_variant.name}'",
                                log_id, True
                            )

        self.env.cr.commit()
        if non_storable_products:
            names = ", ".join(non_storable_products.mapped("name"))
            error_messages.append(f"The following products are not storable and cannot be exported: {names}.")
        if no_sku_products:
            product_names = ', '.join(no_sku_products)
            error_messages.append(f"The following products cannot be exported without SKU: {product_names}")

        if no_sku_product_variant:
            variant_names = ', '.join(no_sku_product_variant)
            error_messages.append(
                f"The following product variant cannot be exported without SKU: [{variant_names}]")

        if error_messages:
            raise ValidationError('\n'.join(error_messages))