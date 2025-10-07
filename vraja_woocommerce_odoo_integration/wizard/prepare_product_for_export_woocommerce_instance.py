import logging
from odoo import fields,models
from odoo.exceptions import UserError

_logger = logging.getLogger("woocommerce")

class PrepareProductForExportWoocommerceInstance(models.TransientModel):
    _name = "prepare.product.for.export.woocommerce.instance"
    _description = "Export Product Woocommerce Instance Wizard"

    woocommerce_instance_id = fields.Many2one('woocommerce.instance.integration',string="Woocomerce Instance")

    def prepare_product_for_export_woocommerce_instance(self):
        try:
            woocommerce_instance = self.woocommerce_instance_id
            failed_product = 0
            log_id = self.env['woocommerce.log'].generate_woocommerce_logs('product', 'export', woocommerce_instance,
                                                                   'Process Started')
            active_template_ids = self._context.get("active_ids", [])
            product_templates_ids = self.env["product.template"].browse(active_template_ids)
            product_templates = product_templates_ids.filtered(lambda template: template.detailed_type == "product")
            if not product_templates:
                raise UserError(_("It seems like selected products are not Storable products."))
            woocommerce_template_id = False
            product_variants_ids = product_templates.product_variant_ids

            for variant in product_variants_ids:
                if not variant.default_code:
                    failed_product += 1
                    message = "Product {0} have no SKU value".format(variant.name)
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line('product', 'export', woocommerce_instance,
                                                                               message, False, message, log_id, True)
                    continue
                product_template_id = variant.product_tmpl_id
                if product_template_id.attribute_line_ids and len(product_template_id.attribute_line_ids.filtered(
                        lambda x: x.attribute_id.create_variant == "always")) > 3:
                    continue
                woocommerce_product_listing_obj, woocommerce_template_id = self.env[
                    "woocommerce.product.listing"].create_or_update_woocommerce_listing_from_odoo_product_tmpl(
                    # create or update product method
                    woocommerce_instance, product_template_id, woocommerce_template_id)

                self.env[
                    "woocommerce.product.listing.item"].create_or_update_woocommerce_listing_item_from_odoo_product_variant(
                    variant,
                    woocommerce_template_id,
                    woocommerce_instance,
                    woocommerce_product_listing_obj)
                if product_template_id.image_1920:
                    vals = {
                        'name': woocommerce_product_listing_obj.name,
                        'sequence': 10,
                        'image': product_template_id.image_1920,
                        'woocommerce_listing_id': woocommerce_product_listing_obj.id,
                        'listing_item_ids': [(6, 0, woocommerce_product_listing_obj.woocommerce_product_listing_items.ids)],
                    }
                    self.env['woocommerce.product.image'].create(vals)
            log_id.woocommerce_operation_message = 'Process Has Been Finished'
            if not log_id.woocommerce_operation_line_ids:
                log_id.unlink()
            if failed_product > 0:
                return {
                    'effect': {
                        'fadeout': 'slow',
                        'message': "Some products not exported successfully please check log",
                        'img_url': '/web/static/img/smile.svg',
                        'type': 'rainbow_man',
                    }
                }
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': "Yeah! woocommerce products export successfully!!",
                    'img_url': '/web/static/img/smile.svg',
                    'type': 'rainbow_man',
                }
            }
        except Exception as e:
            _logger.info("Getting an Error : {}".format(e))
