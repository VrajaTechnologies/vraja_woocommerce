from odoo import models, fields
import json


class WoocommerceExportProductCategory(models.TransientModel):
    _name = "woocommerce.export.product.category"

    woocommerce_instance_id = fields.Many2one('woocommerce.instance.integration', string="Woocommerce Instance",required=1)

    def export_product_category(self):
        """export product category to woocommerce"""
        active_cate_ids = self.env.context.get("active_ids", [])
        product_cat_ids = self.env['woocommerce.product.category'].browse(active_cate_ids)
        instance = self.woocommerce_instance_id
        log_id = self.env['woocommerce.log'].generate_woocommerce_logs("product", "export", instance,"Product Export Process Started")
        try:
            remaining_category = product_cat_ids
            exported_count, loop_count = 0, 0
            max_loops = len(remaining_category) + 1
            while remaining_category and loop_count < max_loops:
                loop_count += 1
                category_create, category_update = [], []
                category_to_export = remaining_category.filtered(
                    lambda c: (not c.parent_id) or (c.parent_id and c.parent_id.code))
                if not category_to_export:
                    self._log_woocommerce_process("product", "export", instance, "There is no data to export.", log_id,True)
                    break
                for rec in category_to_export:
                    vals = {
                        "name": str(rec.name or ""),
                        "slug": str(rec.slug or ""),
                        "parent": rec.parent_id.code if rec.parent_id else 0,
                        "display": str(rec.display)
                    }
                    if rec.code:
                        vals["id"] = rec.code
                        category_update.append(vals)
                    else:
                        category_create.append(vals)
                batch_data = {"create": category_create, "update": category_update}
                category_vals_json = json.dumps(batch_data)
                wc_api = f"{instance.woocommerce_url}/wp-json/wc/v3/products/categories/batch"
                response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("POST",wc_api,category_vals_json)
                if not response_data or isinstance(response_data, str):
                    self._log_woocommerce_process("product", "export", instance, "Invalid response data from API.",log_id, True)
                    break
                if not response_data.get("create") and not response_data.get("update"):
                    self._log_woocommerce_process("product", "export", instance, "Incomplete response data from API.",log_id, True)
                if response_status:
                    exported_names = []
                    for section in ["create", "update"]:
                        for index, cat in enumerate(response_data.get(section, [])):
                            wc_id, wc_name, wc_slug = cat.get("id"), cat.get("name"), cat.get("slug")
                            if cat.get("error"):
                                error = cat.get("error", {}) or {}
                                error_code = error.get("code")
                                error_data = error.get("data") or {}
                                resource_id = error_data.get("resource_id") if error_data else None
                                if error_code in ["term_exists"]:
                                    if resource_id:
                                        cat_name = batch_data.get(section, [])[index].get("name") if index < len(
                                            batch_data.get(section, [])) else "Unknown"
                                        existing_cat = remaining_category.filtered(
                                            lambda c: not c.code and c.name.strip().lower() == cat_name.strip().lower())
                                        if existing_cat:
                                            remaining_category -= existing_cat
                                            msg = f"product category already created in woocommerce with same name.(Category ID: {resource_id})"
                                            self._log_woocommerce_process("product", "export", instance, msg, log_id,False)
                                            continue
                                if error_code in ["woocommerce_rest_term_invalid", "woocommerce_rest_term_not_found","rest_term_invalid"]:
                                    bad_category = remaining_category.filtered(
                                        lambda c: str(c.code) == str(cat.get("id")))
                                    bad_category.write({"code": False})
                                    continue
                                msg = f"There is some error to export Product Category '{wc_name}'. Response: {response_data}"
                                self._log_woocommerce_process("product", "export", instance, msg, log_id, True)
                                batch_cat_data = batch_data.get(section, [])[index] if index < len(
                                    batch_data.get(section, [])) else {}
                                batch_name, batch_slug = batch_cat_data.get("name"), batch_cat_data.get("slug")
                                failed_category = remaining_category.filtered(
                                    lambda c: (resource_id and str(c.code) == str(resource_id)) or
                                              (wc_id and str(c.code) == str(wc_id)) or
                                              (batch_slug and getattr(c, "slug", "") == batch_slug) or
                                              (batch_name and c.name.strip().lower() == batch_name.strip().lower()))
                                remaining_category -= failed_category
                                continue
                            if not wc_id:
                                continue
                            batch_cat_data = batch_data.get(section, [])[index] if index < len(
                                batch_data.get(section, [])) else {}
                            original_slug = batch_cat_data.get("slug")
                            if wc_slug and original_slug and wc_slug != original_slug:
                                msg = f"WooCommerce auto-renamed slug for '{wc_name}' from '{original_slug}' to '{wc_slug}' (ID: {wc_id})"
                                self._log_woocommerce_process("product", "export", instance, msg, log_id, False)
                                current_cat = remaining_category.filtered(
                                lambda c: c.name == wc_name and c.slug == original_slug)
                                if current_cat:
                                    current_cat.write({"slug": wc_slug, "code": wc_id})
                            odoo_cat = self.env["woocommerce.product.category"].search(['|', '|',
                                                                                        ("code", "=", wc_id),
                                                                                        ("name", "=", wc_name),
                                                                                        ("slug", "=", wc_slug)], limit=1)
                            if odoo_cat:
                                odoo_cat.write({"code": wc_id})
                            else:
                                current_cat = remaining_category.filtered(lambda c: c.name == wc_name)
                                if current_cat:
                                    current_cat.write({"code": wc_id, "slug": wc_slug})
                            msg = f"Product Category '{wc_name}' exported successfully (WooCommerce ID: {wc_id})."
                            self._log_woocommerce_process("product", "export", instance, msg, log_id, False)
                            exported_names.append(wc_name)
                    remaining_category = remaining_category.filtered(lambda c: c.name not in exported_names)
                    exported_count += len(exported_names)
                else:
                    msg = f"Failed to export Product Category to WooCommerce. Response: {response_data}"
                    self._log_woocommerce_process("product", "export", instance, msg, log_id, True)
                    remaining_category -= category_to_export
                    continue
            if loop_count >= max_loops:
                msg = "Something went wrong. Stopped export process to prevent infinite loop."
                self._log_woocommerce_process("product", "export", instance, msg, log_id, True)
        except Exception as e:
            message = f"Exception while exporting Product Category to WooCommerce: {str(e)}"
            self._log_woocommerce_process("product", "export", instance, message, log_id, True)

    def _log_woocommerce_process(self, model, operation, instance, message, log_id, fault_operation):
        self.env['woocommerce.log.line'].generate_woocommerce_process_line(model, operation, instance, message, False, message, log_id, fault_operation)
