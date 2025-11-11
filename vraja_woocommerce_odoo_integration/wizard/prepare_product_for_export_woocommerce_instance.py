import json
from odoo import fields, models
from odoo.exceptions import ValidationError


class PrepareProductForExportWoocommerceInstance(models.TransientModel):
    _name = "prepare.product.for.export.woocommerce.instance"
    _description = "Export Product to WooCommerce Wizard"

    set_price = fields.Boolean(string="Set Price")
    set_image = fields.Boolean(string="Set Image")
    woocommerce_instance_id = fields.Many2one(
        'woocommerce.instance.integration', string="WooCommerce Instance", required=True
    )

    # MAIN EXPORT ENTRY
    def prepare_product_for_export_woocommerce_instance(self):
        """Export or update products and their variants to WooCommerce."""
        instance = self.woocommerce_instance_id
        log_id = self.env["woocommerce.log"].generate_woocommerce_logs(
            "product", "export", instance, "WooCommerce Product Export Started"
        )

        listing_model = self.env["woocommerce.product.listing"]
        variant_model = self.env["woocommerce.product.listing.item"]

        no_sku_products = []
        no_sku_variants = []

        product_templates = self.env["product.template"].browse(self.env.context.get("active_ids", []))

        for product in product_templates:
            # Step 1: Validate SKU presence (simple vs variants)
            if not self._validate_product_sku(product, no_sku_products, no_sku_variants, log_id, instance):
                continue

            # Step 2: Ensure local product listing exists (create if missing)
            wc_product = listing_model.search([
                ("product_tmpl_id", "=", product.id),
                ("woocommerce_instance_id", "=", instance.id)
            ], limit=1)
            if not wc_product:
                wc_product = listing_model.create({
                    "product_tmpl_id": product.id,
                    "woocommerce_instance_id": instance.id,
                    "woocommerce_default_code": product.default_code,
                    "name": product.name,
                    "product_catg_id": product.categ_id.id,
                    "description": product.description_sale or "",
                    "exported_in_woocommerce": False,
                })
                self._log(instance, log_id, f"🆕 Local listing created for '{product.name}'")

            # Step 3: Export or update main product to WooCommerce (sync main product first)
            exported_ok = self._export_main_product_to_wc(product, wc_product, instance, log_id)
            if not exported_ok:
                # If main product couldn't be created/updated on WooCommerce, skip variants
                continue

            # Step 4: Sync local variant listing items (create/update only for variants that have SKU)
            self._sync_local_variants(product, wc_product, variant_model, no_sku_variants, log_id, instance)

            # Step 5: Export variants to WooCommerce (only for variable products)
            if len(product.product_variant_ids) > 1:
                self._export_variants_to_wc(product, wc_product, variant_model, instance, log_id, no_sku_variants)
            else:
                # simple product — nothing more to do for variants
                self._log(instance, log_id, f"ℹ️ Product '{product.name}' is simple; no variant export required.")
        self.env.cr.commit()
        # Final: raise collected errors (if any)
        self._raise_export_errors(no_sku_products, no_sku_variants)
        # commit optionally if you want immediate DB persist: self.env.cr.commit()
        return True

    # SKU VALIDATION
    def _validate_product_sku(self, product, no_sku_products, no_sku_variants, log_id, instance):
        """
        Validate SKUs before exporting.
        - Simple product: requires template.default_code
        - Variant product: at least one variant must have a SKU (we still accept partial)
        """
        # Simple product
        if not product.attribute_line_ids:
            if not product.default_code:
                no_sku_products.append(product.name)
                self._log(instance, log_id, f"❌ Simple product '{product.name}' has no SKU — skipped.", error=True)
                return False
            return True

        # Product has variants
        variants = product.product_variant_ids
        missing = variants.filtered(lambda v: not v.default_code)
        if len(missing) == len(variants):
            # All variants missing SKUs -> skip entire product
            no_sku_products.append(product.name)
            self._log(instance, log_id, f"❌ All variants for '{product.name}' are missing SKUs — skipped.", error=True)
            return False

        if missing:
            # Partial missing: log and record variant names (but proceed)
            missing_names = missing.mapped("display_name")
            no_sku_variants.extend(missing_names)
            self._log(instance, log_id,
                      f"⚠️ Product '{product.name}' has variants missing SKUs: {', '.join(missing_names)}")
        return True

    # EXPORT MAIN PRODUCT (create/update on WooCommerce)
    def _export_main_product_to_wc(self, product, wc_product, instance, log_id):
        """
        Create or update the main product in WooCommerce.
        Writes the returned WooCommerce product id into wc_product.woocommerce_product_id.
        Returns True on success, False on failure.
        """
        base_api = f"{instance.woocommerce_url}/wp-json/wc/v3/products"
        is_variable = len(product.product_variant_ids) > 1

        payload = self._prepare_wc_product_payload(product, is_variable)

        # Decide create or update
        if wc_product.woocommerce_product_id:
            api_url = f"{base_api}/{wc_product.woocommerce_product_id}"
            method = "POST"
            action = "update"
        else:
            api_url = base_api
            method = "POST"
            action = "create"

        try:
            status, data, _ = instance.woocommerce_api_calling_process(method, api_url, json.dumps(payload),
                                                                       "per_page=100")
            # normalize response
            if isinstance(data, str):
                try:
                    data = json.loads(data or "{}")
                except Exception:
                    data = {}
            if status and isinstance(data, dict) and data.get("id"):
                wc_product.write({
                    "woocommerce_product_id": data.get("id"),
                    "exported_in_woocommerce": True,
                })
                self._log(instance, log_id,
                          f"✅ Product '{product.name}' {action}d on WooCommerce (ID: {data.get('id')}).")
                return True
            else:
                self._log(instance, log_id, f"❌ Failed to {action} product '{product.name}': {data}", error=True)
                return False

        except Exception as e:
            self._log(instance, log_id, f"⚠️ Exception while trying to {action} product '{product.name}': {e}",
                      error=True)
            return False

    # PREPARE PRODUCT PAYLOAD
    def _prepare_wc_product_payload(self, product, is_variable=False):
        """
        Build the product payload for WooCommerce API for template/product.
        For variable product include attributes.
        """
        payload = {
            "name": product.name,
            "sku": product.default_code or "",
            "type": "variable" if is_variable else "simple",
            "description": product.description_sale or product.description or "",
            "regular_price": str(product.list_price or product.standard_price or "0.0"),
        }
        if self.set_price and product.list_price:
            payload["price"] = str(product.list_price)

        # include attributes for variable products: pass all combinations / options
        if is_variable:
            attrs = []
            for line in product.attribute_line_ids:
                # normalize attribute name and include all options
                attr_name = (line.attribute_id.name or "").strip()
                options = [(v.name or "").strip() for v in line.value_ids]

                # only include attribute if it has options
                if options:
                    attrs.append({
                        "name": attr_name,
                        "options": options,
                        # ✅ mark variation=True only if more than one option exists
                        # (e.g. Color, Size) else keep False for static attributes like Brand
                        "variation": len(options) > 1,
                        "visible": True,
                    })
            payload["attributes"] = attrs

        # image handling omitted; add if set_image is required
        return payload

    # SYNC LOCAL VARIANT LISTING ITEMS (only for variants with SKU)
    def _sync_local_variants(self, product, wc_product, variant_model, no_sku_variants, log_id, instance):
        """
        Ensure local variant listing items exist for each variant that has an SKU.
        Do not create listing items for variants without SKU.
        """
        # if not variable product, do nothing
        if len(product.product_variant_ids) <= 1:
            return

        for variant in product.product_variant_ids:
            if not variant.default_code:
                # collect already done earlier; skip
                continue

            vals = {
                "name": variant.display_name,
                "product_id": variant.id,
                "product_sku": variant.default_code,
                "woocommerce_product_listing_id": wc_product.id,
                "woocommerce_instance_id": instance.id,
            }
            wc_variant = variant_model.search([
                ("product_id", "=", variant.id),
                ("woocommerce_product_listing_id", "=", wc_product.id)
            ], limit=1)
            if wc_variant:
                wc_variant.write(vals)
                self._log(instance, log_id, f"🔄 Local variant listing updated: {variant.display_name}")
            else:
                variant_model.create(vals)
                self._log(instance, log_id, f"🆕 Local variant listing created: {variant.display_name}")

    # EXPORT VARIANTS TO WOO (only called after main product exported)
    def _export_variants_to_wc(self, product, wc_product, variant_model, instance, log_id, no_sku_variants):
        """
        Export or update product variants to the WooCommerce product/{id}/variations endpoint.
        """
        base_api = f"{instance.woocommerce_url}/wp-json/wc/v3/products"

        # safety: parent product id must exist
        if not wc_product.woocommerce_product_id:
            self._log(instance, log_id,
                      f"❌ Parent WooCommerce product missing for '{product.name}' — cannot export variants", error=True)
            return

        for variant in product.product_variant_ids:
            if not variant.default_code:
                # recorded earlier; ensure listed
                if variant.display_name not in no_sku_variants:
                    no_sku_variants.append(variant.display_name)
                self._log(instance, log_id, f"⏭️ Skipping variant '{variant.display_name}' — no SKU.")
                continue

            # find local listing item
            wc_variant = variant_model.search([
                ("product_id", "=", variant.id),
                ("woocommerce_product_listing_id", "=", wc_product.id)
            ], limit=1)

            if not wc_variant:
                wc_variant = variant_model.create({
                    "product_id": variant.id,
                    "woocommerce_product_listing_id": wc_product.id,
                    "product_sku": variant.default_code,
                    "exported_in_woocommerce": False,
                })

            payload = self._prepare_wc_variant_payload(variant)

            # determine create or update
            api_url = f"{base_api}/{wc_product.woocommerce_product_id}/variations"
            method = "POST"
            action = "create"
            if wc_variant.woocommerce_product_variant_id:
                api_url = f"{api_url}/{wc_variant.woocommerce_product_variant_id}"
                method = "POST"
                action = "update"

            try:
                status, data, _ = instance.woocommerce_api_calling_process(method, api_url, json.dumps(payload),"per_page=100")
                if isinstance(data, str):
                    try:
                        data = json.loads(data or "{}")
                    except Exception:
                        data = {}

                if status and isinstance(data, dict) and data.get("id"):
                    wc_variant.write({
                        "woocommerce_product_variant_id": data.get("id"),
                        "exported_in_woocommerce": True,
                    })
                    self._log(instance, log_id,
                              f"✅ Variant '{variant.display_name}' {action}d (Woo ID: {data.get('id')}).")
                else:
                    self._log(instance, log_id, f"❌ Failed to {action} variant '{variant.display_name}': {data}",
                              error=True)

            except Exception as e:
                self._log(instance, log_id, f"⚠️ Exception while {action} variant '{variant.display_name}': {e}",
                          error=True)

    # PREPARE VARIANT PAYLOAD
    def _prepare_wc_variant_payload(self, variant):
        """Prepare variant payload for WooCommerce."""
        # make sure attribute names/options exactly match what we sent in product attributes
        attributes_payload = []
        product_tmpl = variant.product_tmpl_id

        # collect variant-specific values (e.g. Color, Size)
        for val in variant.product_template_variant_value_ids:
            attr_name = (val.attribute_id.name or "").strip()
            option = (val.name or "").strip()
            if attr_name and option:
                attributes_payload.append({
                    "name": attr_name,
                    "option": option,
                })

        # ✅ include static (single-value) attributes like "Brand"
        for line in product_tmpl.attribute_line_ids:
            attr_name = (line.attribute_id.name or "").strip()
            if not any(a["name"] == attr_name for a in attributes_payload):
                # if this attribute wasn't added from variant values, use its single option
                if len(line.value_ids) == 1:
                    attributes_payload.append({
                        "name": attr_name,
                        "option": (line.value_ids[0].name or "").strip(),
                    })

        payload = {
            "sku": variant.default_code or "",
            "regular_price": str(variant.list_price or "0.0"),
            "manage_stock": True,
            "stock_quantity": int(variant.qty_available or 0),
            # attributes: must match product-level attribute names/options
            "attributes": attributes_payload,
        }

        if self.set_price and variant.list_price:
            payload["price"] = str(variant.list_price)

        return payload

    # ERROR AGGREGATION
    def _raise_export_errors(self, no_sku_products, no_sku_variants):
        msgs = []
        if no_sku_products:
            msgs.append("❌ Missing SKU on Products:\n" + "\n".join(no_sku_products))
        if no_sku_variants:
            msgs.append("⚠️ Missing SKU on Variants:\n" + "\n".join(no_sku_variants))
        if msgs:
            raise ValidationError("\n\n".join(msgs))

    # LOG HELPER
    def _log(self, instance, log_id, message, error=False):
        """Centralized logger."""
        self.env["woocommerce.log.line"].generate_woocommerce_process_line(
            "product", "export", instance, message, False, message, log_id, error
        )
