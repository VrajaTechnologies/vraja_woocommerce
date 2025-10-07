import base64
import pytz
import logging
import requests
from dateutil import parser
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger("Import Order Process:")
utc = pytz.utc


class WooCommerceProductListing(models.Model):
    _name = 'woocommerce.product.listing'
    _description = 'WooCommerce Product Listing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    def export_woocommerce_product(self):
        return {
            'name': 'Woocommerce - Export Product',
            'type': 'ir.actions.act_window',
            'res_model': 'export.woocommerce.product',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': self.ids},
        }

    def update_woocommerce_product(self):
        return {
            'name': 'Woocommerce - Update Product',
            'type': 'ir.actions.act_window',
            'res_model': 'update.woocommerce.product',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_ids': self.ids},
        }

    def compute_count_of_woocommerce_product_variants(self):
        """
        This method is used to count total variants in product listing module.
        """
        for rec in self:
            rec.total_variants_in_woocommerce = len(rec.woocommerce_product_listing_items)

    name = fields.Char(string='Name')
    woocommerce_instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance')
    product_tmpl_id = fields.Many2one('product.template', string="Product Template")
    product_catg_id = fields.Many2one('product.category', string="Product Category")
    woocommerce_default_code = fields.Char(string="SKU", copy=False)
    woocommerce_product_id = fields.Char(string="Woocommerce Product ID")
    description = fields.Text(string="Description")
    last_sync_date = fields.Datetime(string="Last Synced", copy=False)
    woocommerce_product_listing_items = fields.One2many('woocommerce.product.listing.item',
                                                        'woocommerce_product_listing_id',
                                                        string='Product Listing Items')
    product_data_queue_id = fields.Many2one('woocommerce.product.data.queue', string='Product Queue')

    tag_ids = fields.Many2many("woocommerce.product.tags", "woocommerce_tags_rel", "listing_id",
                               "tag_id", "Woocommerce Tags")

    # website_published = fields.Selection([('unpublished', 'Unpublished'), ('published_web', 'Published in Web Only'),
    #                                       ('published_global', 'Published in Web and POS')],
    #                                      default='unpublished', copy=False, string="Published ?")
    exported_in_woocommerce = fields.Boolean(default=False)
    total_variants_in_woocommerce = fields.Integer("Total Variants",
                                                   compute="compute_count_of_woocommerce_product_variants")

    # published_at = fields.Datetime("Published Date")
    image_ids = fields.One2many('woocommerce.product.image', 'woocommerce_listing_id', 'Images')
    #
    # def sync_product_image_from_shopify(self, shopify_instance_id, shopify_listing_id, shopify_product_dict):
    #     shopify_image_response_vals = shopify_product_dict.get('images', {})
    #     shopify_product_image = self.env['shopify.product.image']
    #     shopify_listing_item_obj = self.env['shopify.product.listing.item']
    #     if not shopify_image_response_vals:
    #         shopify_instance_id.test_shopify_connection()
    #         images = shopify.Image().find(product_id=shopify_listing_id.shopify_product_id)
    #         shopify_image_response_vals = [image.to_dict() for image in images]
    #     for image in shopify_image_response_vals:
    #         image_url = image.get('src')
    #         if image_url:
    #             variant_ids, shopify_image_id = image.get('variant_ids'), image.get('id')
    #             shopify_listing_item_ids = shopify_listing_item_obj.search(
    #                 [('shopify_instance_id', '=', shopify_instance_id.id),
    #                  ('shopify_product_listing_id', 'in', variant_ids)])
    #             listing_image_id = shopify_product_image.search([('shopify_image_id', '=', shopify_image_id)])
    #             image_datas = base64.b64encode(requests.get(image_url).content)
    #             vals = {
    #                 'name': shopify_listing_id.name,
    #                 'shopify_image_id': shopify_image_id,
    #                 'sequence': image.get('position'),
    #                 'image': image_datas,
    #                 'shopify_listing_id': shopify_listing_id.id,
    #                 'listing_item_ids': [(6, 0, shopify_listing_item_ids.ids)],
    #             }
    #             if listing_image_id:
    #                 listing_image_id.write(vals)
    #             else:
    #                 shopify_product_image.create(vals)
    #
    #             for listing_item in shopify_listing_item_ids:
    #                 listing_item.product_id.write({'image_1920': image_datas})
    #
    #             if image.get('position') == 1:
    #                 shopify_listing_id.product_tmpl_id.write({'image_1920': image_datas})
    #     return True
    #
    # def update_shopify_product_images(self, log_id, instance, product_type):
    #     """
    #     Export OR Update Images From Odoo To Shopify.
    #     While Export OR Update Product First Fetch all the Product From Shopify If There is no Images Inside odoo, so we Destroy the Images in Shopify For that Listing.
    #     Inside Listing Images available and Shopify Image ID not Set that we Export it to Shopify.
    #     If Shopify Image ID Set then we Update the Data From odoo to Shopify.
    #     After all process complete Check In Shopify Is there any Extra Images available If yes then we Destroy in Shopify (Compare with odoo listing image)
    #     """
    #     self.ensure_one()
    #
    #     # Deleting listing images in Shopify if no images available in Odoo.
    #     shopify_images = shopify.Image().find(product_id=self.shopify_product_id)
    #     if not self.image_ids and shopify_images:
    #         for shop_image in shopify_images:
    #             shop_image.destroy()
    #         return False
    #     for image_id in self.image_ids:
    #         if not image_id.shopify_image_id and image_id.image:
    #             shopify_image = shopify.Image()
    #             shopify_image.product_id = self.shopify_product_id
    #             shopify_image.position = image_id.sequence
    #             shopify_image.attachment = image_id.image.decode('UTF-8')
    #             # shopify_image.alt = image_id.shopify_alt_text or ''
    #             shopify_image.variant_ids = image_id.listing_item_ids.mapped('shopify_product_variant_id')
    #             response = shopify_image.save()
    #             if response:
    #                 image_id.shopify_image_id = shopify_image.id
    #                 message = 'Shopify Image ID : {}'.format(shopify_image.id)
    #                 self.env['shopify.log.line'].generate_shopify_process_line('product', product_type, instance,
    #                                                                            message,
    #                                                                            False, message, log_id, False)
    #         else:
    #             for shopify_image in shopify_images:
    #                 if int(image_id.shopify_image_id) == shopify_image.id:
    #                     shopify_image.id = shopify_image.id
    #                     shopify_image.position = image_id.sequence
    #                     # shopify_image.alt = image_id.shopify_alt_text or ''
    #                     shopify_image.attachment = image_id.image.decode('UTF-8')
    #                     response = shopify_image.save()
    #                     if response:
    #                         message = 'Shopify Image ID : {}'.format(shopify_image.id)
    #                         self.env['shopify.log.line'].generate_shopify_process_line('product', product_type,
    #                                                                                    instance,
    #                                                                                    message,
    #                                                                                    False, message, log_id, False)
    #                     break
    #
    #     # Deleting listing images in Shopify that will not exist in Odoo.
    #     odoo_shopify_images = self.image_ids.mapped('shopify_image_id')
    #     for shop_image in shopify_images:
    #         if not str(shop_image.id) in odoo_shopify_images:
    #             shop_image.destroy()
    #     return True
    #
    def get_odoo_product_category(self, product_type):
        """
        This method is used to find Product category & if not found then create new one.
        """
        product_category_obj = self.env["product.category"]
        product_category = product_category_obj.search([
            "|",
            "&", ("name", "=", product_type), ("woocommerce_product_cat", "=", True),
            "&", ("name", "=", product_type.lower()), ("woocommerce_product_cat", "=", True)
        ], limit=1)

        if not product_category:
            product_category = product_category_obj.search([("name", "=", product_type.lower())], limit=1)
            if product_category:
                product_category.woocommerce_product_cat = True
        else:
            product_category = product_category[0]  # Since it's a single result due to limit=1

        if not product_category:
            product_category = product_category_obj.create({"name": product_type, "woocommerce_product_cat": True})
        return product_category

    #
    def convert_woocommerce_date_into_odoo_date_format(self, product_date):
        """
        This method used to convert product date into actual date time format
        :return date
        """
        if not product_date:
            return False
        woocommerce_product_date = parser.parse(product_date).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
        return woocommerce_product_date

    # def prepare_woocommerce_product_listing_vals(self, product_data, instance, product_category):
    #     """
    #     This method is designed for crafting values for a Shopify product listing.
    #     """
    #     woocommerce_tag_obj = self.env["woocommerce.product.tags"]
    #     tag_ids = []
    #     sequence = 0
    #
    #     def convert_date(key):
    #         return self.convert_woocommerce_date_into_odoo_date_format(product_data.get(key))
    #
    #     website_published = "unpublished"
    #     if product_data.get('status'):
    #         website_published = product_data.get("status")
    #
    #     if product_data.get("tags"):
    #         for tag in product_data.get("tags"):
    #             woocommerce_tag = woocommerce_tag_obj.search([("name", "=", tag.get('name'))], limit=1)
    #             if not woocommerce_tag:
    #                 sequence += 1
    #                 woocommerce_tag = woocommerce_tag_obj.create({"name": tag, "sequence": sequence})
    #             sequence = woocommerce_tag.sequence if woocommerce_tag else 0
    #             tag_ids.append(woocommerce_tag.id)
    #
    #     # product_listing_vals = {
    #     #     "woocommerce_instance_id": instance.id,
    #     #     "name": product_data.get("name"),
    #     #     "body_html": product_data.get("description"),
    #     #     # "product_type": product_data.get("product_type"),
    #     #     "tags": tag_ids,
    #     #     "woocommerce_tmpl_id": product_data.get("id"),
    #     #     "woocommerce_product_category": product_category.id if product_category else False,
    #     #     "created_at": convert_date("date_created"),
    #     #     "updated_at": convert_date("date_modified"),
    #     #     # "published_at": convert_date("published_at"),
    #     #     "website_published": website_published,
    #     #     "active": True
    #     # }
    #     # return product_listing_vals
    #
    #     return {
    #         "name": product_data.get("name"),
    #         "woocommerce_instance_id": instance.id,
    #         "product_tmpl_id": False,  # You can link to an Odoo product template if needed
    #         "product_catg_id": product_category.id if product_category else False,
    #         "woocommerce_product_id": str(product_data.get("id")),
    #         "description": product_data.get("description"),
    #         "last_sync_date": fields.Datetime.now(),
    #     }

    #
    # def prepare_product_listing_item_vals(self, instance, woocommerce_variant_data):
    #     """
    #     Prepare Woocommerce product listing item values.
    #     """
    #     convert_date = lambda key: self.convert_woocommerce_date_into_odoo_date_format(
    #         woocommerce_variant_data.get(key))
    #
    #     product_listing_item_vals = {
    #         "create_date": convert_date("created_at"),
    #         "write_date": convert_date("updated_at"),
    #         "exported_in_shopify": True,
    #         "active": True,
    #         "shopify_instance_id": instance.id,
    #         "shopify_product_variant_id": woocommerce_variant_data.get("id"),
    #         "sequence": woocommerce_variant_data.get("position"),
    #         "product_sku": woocommerce_variant_data.get("sku", ""),
    #         "taxable": woocommerce_variant_data.get("taxable"),
    #         "inventory_item_id": woocommerce_variant_data.get("inventory_item_id"),
    #         "inventory_management": "shopify" if woocommerce_variant_data.get(
    #             "inventory_management") == "shopify" else "Dont track Inventory",
    #         "inventory_policy": woocommerce_variant_data.get("inventory_policy")
    #     }
    #     return product_listing_item_vals

    #
    # def create_or_update_shopify_product_listing_item(self, product_listing_item_vals, shopify_product_listing_item,
    #                                                   shopify_product_listing=False, odoo_product_variant=False):
    #     """
    #     Create a new shopify variant into Odoo or update an existing one.
    #     """
    #     shopify_product_listing_item_obj = self.env["shopify.product.listing.item"]
    #     if not shopify_product_listing_item and shopify_product_listing and odoo_product_variant:
    #         product_listing_item_vals.update({"name": odoo_product_variant.name,
    #                                           "product_id": odoo_product_variant.id,
    #                                           "shopify_product_listing_id": shopify_product_listing.id})
    #         shopify_product_listing_item = shopify_product_listing_item_obj.create(product_listing_item_vals)
    #         if not odoo_product_variant.default_code:
    #             odoo_product_variant.default_code = shopify_product_listing_item.product_sku
    #     elif shopify_product_listing_item:
    #         shopify_product_listing_item.write(product_listing_item_vals)
    #     return shopify_product_listing_item
    #
    # def shopify_create_product_without_variant(self, product_name, variant_data, attribute_line_data=[]):
    #     """
    #     Create product without variants.
    #     """
    #     odoo_product_variant = self.env["product.product"]
    #     product_sku = variant_data.get("sku", "")
    #     barcode = variant_data.get("barcode")
    #     if product_sku or barcode:
    #         vals = {
    #             "name": product_name,
    #             "detailed_type": "product",
    #             "default_code": product_sku,
    #             "invoice_policy": "order",
    #             **({"barcode": barcode} if barcode else {})
    #         }
    #         odoo_product_variant = odoo_product_variant.create(vals)
    #         if attribute_line_data:
    #             odoo_product_variant.product_tmpl_id.write({"attribute_line_ids": attribute_line_data})
    #     return odoo_product_variant
    #
    # @api.model
    # def retrieve_template_attribute_values(self, template_options, product_template_id, variant):
    #     """
    #     Create a domain for template attribute values from product.template.attribute.value.
    #     """
    #     product_attribute_obj = self.env["product.attribute"]
    #     template_attribute_value_domain = []
    #
    #     for counter, attribute in enumerate(template_options, start=1):
    #         product_attribute = product_attribute_obj.get_attribute(attribute.get("name"), auto_create=True)[0]
    #         attribute_name = "option" + str(counter)
    #         attribute_val = variant.get(attribute_name)
    #
    #         product_attribute_value_obj = self.env["product.attribute.value"]
    #         product_template_attribute_value_obj = self.env["product.template.attribute.value"]
    #
    #         product_attribute_value = product_attribute_value_obj.get_attribute_values(attribute_val,
    #                                                                                    product_attribute.id,
    #                                                                                    auto_create=True)
    #
    #         if product_attribute_value:
    #             product_attribute_value = product_attribute_value[0]
    #             template_attribute_value_id = product_template_attribute_value_obj.search(
    #                 [("product_attribute_value_id", "=", product_attribute_value.id),
    #                  ("attribute_id", "=", product_attribute.id),
    #                  ("product_tmpl_id", "=", product_template_id)], limit=1)
    #
    #             if template_attribute_value_id:
    #                 template_attribute_value_domain.append(
    #                     ("product_template_attribute_value_ids", "=", template_attribute_value_id.id))
    #
    #     return template_attribute_value_domain if len(template_options) == len(template_attribute_value_domain) else []
    #
    # def create_or_update_shopify_product_listing(self, product_listing_vals, shopify_product_listing,
    #                                              odoo_product_variant=False, odoo_product_template=False):
    #     """
    #     Create new or update existing Shopify template in Odoo.
    #     @param: product_listing_vals, shopify_product_listing, odoo_product_variant
    #     @return: shopify_product_listing
    #     """
    #     vals = {
    #         "shopify_instance_id": product_listing_vals.get("shopify_instance_id"),
    #         "name": product_listing_vals.get("template_title"),
    #         "shopify_product_id": product_listing_vals.get("shopify_tmpl_id"),
    #         "create_date": product_listing_vals.get("created_at"),
    #         "write_date": product_listing_vals.get("updated_at"),
    #         "description": product_listing_vals.get("body_html"),
    #         "published_at": product_listing_vals.get("published_at"),
    #         "website_published": product_listing_vals.get("website_published"),
    #         "exported_in_shopify": True,
    #         "product_catg_id": product_listing_vals.get("shopify_product_category"),
    #     }
    #     if shopify_product_listing:
    #         shopify_product_listing.write(vals)
    #     else:
    #         product_tmpl_id = odoo_product_variant.product_tmpl_id.id if odoo_product_variant else (
    #             odoo_product_template.id if odoo_product_template else None
    #         )
    #         vals.update({"product_tmpl_id": product_tmpl_id})
    #         shopify_product_listing = self.create(vals)
    #     return shopify_product_listing
    #
    # def create_or_update_shopify_product_listing_and_listing_item(self, product_listing_vals, product_listing_item_vals,
    #                                                               shopify_product_listing, shopify_product_listing_item,
    #                                                               odoo_product_variant, update_product_listing=False,
    #                                                               update_product_listing_item=False):
    #     """
    #     This method is used to create or update shopify template and/or variant.
    #     """
    #     if update_product_listing:
    #         shopify_product_listing = self.create_or_update_shopify_product_listing(product_listing_vals,
    #                                                                                 shopify_product_listing,
    #                                                                                 odoo_product_variant)
    #     if update_product_listing_item:
    #         shopify_product_listing_item = self.create_or_update_shopify_product_listing_item(product_listing_item_vals,
    #                                                                                           shopify_product_listing_item,
    #                                                                                           shopify_product_listing,
    #                                                                                           odoo_product_variant)
    #     return shopify_product_listing, shopify_product_listing_item
    #
    # def sync_odoo_product_variant(self, odoo_product_template, shopify_attributes, variant_data,
    #                               shopify_product_listing, product_listing_item_vals):
    #     """
    #     Check for new attributes and generate a new variant in Odoo.
    #     """
    #     product_attribute_value_obj = self.env["product.attribute.value"]
    #     odoo_product_obj = self.env["product.product"]
    #
    #     product_sku = variant_data.get("sku")
    #     odoo_attribute_lines = odoo_product_template.attribute_line_ids.filtered(
    #         lambda x: x.attribute_id.create_variant == "always")
    #     if len(odoo_attribute_lines) != len(shopify_attributes):
    #         return "Product %s has tried to add a new attribute for SKU %s in Odoo." % (
    #             shopify_product_listing.name, product_sku
    #         )
    #     attribute_value_domain = self.retrieve_template_attribute_values(shopify_attributes, odoo_product_template.id,
    #                                                                      variant_data)
    #     if not attribute_value_domain:
    #         counter = 0
    #         for shopify_attribute in shopify_attributes:
    #             counter += 1
    #             attribute_name = "option" + str(counter)
    #             attribute_value = variant_data.get(attribute_name)
    #
    #             attribute_id = odoo_attribute_lines.filtered(
    #                 lambda x: x.display_name == shopify_attribute.get("name")).attribute_id.id
    #             value_id = product_attribute_value_obj.get_attribute_values(
    #                 attribute_value, attribute_id, auto_create=True
    #             )[0].id
    #
    #             attribute_line = odoo_attribute_lines.filtered(lambda x: x.attribute_id.id == attribute_id)
    #             if value_id not in attribute_line.value_ids.ids:
    #                 attribute_line.value_ids = [(4, value_id, False)]
    #         odoo_product_template._create_variant_ids()
    #
    #     attribute_value_domain = self.retrieve_template_attribute_values(shopify_attributes, odoo_product_template.id,
    #                                                                      variant_data)
    #     odoo_product_variant = odoo_product_obj.search(attribute_value_domain)
    #
    #     if not odoo_product_variant:
    #         return "Unknown error occurred. Couldn't find product %s with SKU %s in Odoo." % (
    #             shopify_product_listing.name, product_sku
    #         )
    #     shopify_product_listing_item = self.create_or_update_shopify_product_listing_item(
    #         product_listing_item_vals, False, shopify_product_listing, odoo_product_variant
    #     )
    #     return shopify_product_listing_item
    #
    # def generate_variant_attribute_line_data(self, shopify_attributes, variant_data):
    #     """
    #     Prepare attribute line data for creating a product with a single variant.
    #     @param shopify_attributes: Attribute data of Shopify template.
    #     @param variant_data: Data of the variant.
    #     """
    #     product_attribute_obj = self.env['product.attribute']
    #     product_attribute_value_obj = self.env['product.attribute.value']
    #
    #     attribute_line_data = []
    #
    #     for counter, shopify_attribute in enumerate(shopify_attributes, start=1):
    #         attribute_name = "option" + str(counter)
    #         shopify_attribute_value = variant_data.get(attribute_name)
    #
    #         attribute = product_attribute_obj.get_attribute(shopify_attribute.get("name"), auto_create=True)
    #         attribute_value = product_attribute_value_obj.get_attribute_values(shopify_attribute_value, attribute.id,
    #                                                                            auto_create=True)
    #         if attribute_value:
    #             attribute_line_data.append(
    #                 (0, False, {'attribute_id': attribute.id, 'value_ids': [[6, False, attribute_value.ids]]})
    #             )
    #     return attribute_line_data
    #
    # def create_new_product_listing(self, product_data, instance, product_category, log_id, product_queue_line):
    #     """
    #     This function serves the purpose of bringing in new products from Woocommerce to Odoo.
    #     """
    #     need_to_update_woocommerce_product_listing = True
    #     woocommerce_product_listing = False
    #
    #     product_listing_vals = self.prepare_woocommerce_product_listing_vals(product_data, instance, product_category)
    #     product_listing_vals.update({"woocommerce_default_code": product_data.get('sku')})
    #     name = product_listing_vals.get("template_title")
    #     odoo_product_template = False
    #
    #     variant_data = product_data.get("variants")
    #     for variant in variant_data:
    #         variant_id = variant.get("id")
    #         product_sku = variant.get("sku")
    #
    #         if not product_sku:
    #             message = "Product %s have no sku having variant id %s." % (name, variant_id)
    #             _logger.info(message)
    #             self.env['woocommerce.log.line'].with_context(
    #                 for_variant_line=product_queue_line).generate_shopify_process_line('product', 'import', instance,
    #                                                                                    message, False, False, log_id,
    #                                                                                    True)
    #             if product_queue_line:
    #                 product_queue_line.state = 'failed'
    #             continue
    #
    #         product_listing_item_vals = self.prepare_product_listing_item_vals(instance, variant)
    #
    #         odoo_product_variant = self.env["product.product"]
    #         shopify_product_listing_item_obj = self.env["shopify.product.listing.item"]
    #
    #         shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #             [("shopify_product_variant_id", "=", variant_id), ("shopify_instance_id", "=", instance.id)], limit=1)
    #         if product_sku:
    #             if not shopify_product_listing_item:
    #                 shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #                     [("product_sku", "=", product_sku), ("shopify_product_variant_id", "=", False),
    #                      ("shopify_instance_id", "=", instance.id)], limit=1)
    #             if not shopify_product_listing_item:
    #                 shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #                     [("product_id.default_code", "=", product_sku), ("shopify_product_variant_id", "=", False),
    #                      ("shopify_instance_id", "=", instance.id)], limit=1)
    #             if not shopify_product_listing_item:
    #                 odoo_product_variant = odoo_product_variant.search([("default_code", "=", product_sku)], limit=1)
    #         if shopify_product_listing_item and not odoo_product_variant:
    #             odoo_product_variant = shopify_product_listing_item.product_id
    #         if odoo_product_variant:
    #             odoo_product_template = odoo_product_variant.product_tmpl_id
    #
    #         if shopify_product_listing_item:
    #             self.create_or_update_shopify_product_listing_item(product_listing_item_vals,
    #                                                                shopify_product_listing_item)
    #             if need_to_update_shopify_product_listing:
    #                 shopify_product_listing = self.create_or_update_shopify_product_listing(product_listing_vals,
    #                                                                                         shopify_product_listing_item.shopify_product_listing_id,
    #                                                                                         odoo_product_variant, False)
    #         elif odoo_product_variant:
    #             shopify_product_listing, shopify_product_listing_item = self.create_or_update_shopify_product_listing_and_listing_item(
    #                 product_listing_vals, product_listing_item_vals, shopify_product_listing,
    #                 shopify_product_listing_item, odoo_product_variant,
    #                 update_product_listing=need_to_update_shopify_product_listing, update_product_listing_item=True)
    #             need_to_update_shopify_product_listing = False
    #
    #         # If odoo's product or shopify listing & listing item not matched with response
    #         # then need to create new product in odoo or not.
    #         elif instance.woocommerce_create_product_if_not_found:
    #             shopify_attributes = product_data.get("options")
    #             if odoo_product_template and odoo_product_template.attribute_line_ids:
    #                 if not shopify_product_listing:
    #                     shopify_product_listing = self.create_or_update_shopify_product_listing(product_listing_vals,
    #                                                                                             False, False,
    #                                                                                             odoo_product_template)
    #                 shopify_product_listing_item = self.sync_odoo_product_variant(odoo_product_template,
    #                                                                               shopify_attributes,
    #                                                                               variant, shopify_product_listing,
    #                                                                               product_listing_item_vals)
    #                 need_to_update_shopify_product_listing = False
    #             else:
    #                 if shopify_attributes[0].get("name") == "Title" and \
    #                         shopify_attributes[0].get("values") == ["Default Title"] and len(variant_data) == 1:
    #                     odoo_product_variant = self.shopify_create_product_without_variant(name, variant,
    #                                                                                        product_listing_vals.get(
    #                                                                                            "body_html"))
    #                 else:
    #                     odoo_product_template = shopify_product_listing_item_obj.shopify_create_product_with_variant(
    #                         product_data)
    #                     attribute_value_domain = self.retrieve_template_attribute_values(shopify_attributes,
    #                                                                                      odoo_product_template.id,
    #                                                                                      variant)
    #                     odoo_product_variant = odoo_product_template.product_variant_ids.search(attribute_value_domain)
    #
    #                 shopify_product_listing, shopify_product_listing_item = self.create_or_update_shopify_product_listing_and_listing_item(
    #                     product_listing_vals, product_listing_item_vals, shopify_product_listing,
    #                     shopify_product_listing_item, odoo_product_variant, update_product_listing=True,
    #                     update_product_listing_item=True)
    #                 need_to_update_shopify_product_listing = False
    #             if isinstance(shopify_product_listing_item, str):
    #                 message = shopify_product_listing_item
    #                 _logger.info(message)
    #                 self.env['shopify.log.line'].with_context(
    #                     for_variant_line=product_queue_line).generate_shopify_process_line('product', 'import',
    #                                                                                        instance,
    #                                                                                        message, False, False,
    #                                                                                        log_id, True)
    #                 if product_queue_line:
    #                     product_queue_line.state = 'failed'
    #                 continue
    #         else:
    #             message = "Product %s not found for SKU %s in Odoo." % (name, product_sku)
    #             _logger.info(message)
    #             self.env['shopify.log.line'].with_context(
    #                 for_variant_line=product_queue_line).generate_shopify_process_line('product', 'import', instance,
    #                                                                                    message, False, False, log_id,
    #                                                                                    True)
    #             if product_queue_line:
    #                 product_queue_line.state = 'failed'
    #             continue
    #
    #         if need_to_update_shopify_product_listing and shopify_product_listing:
    #             shopify_product_listing = self.create_or_update_shopify_product_listing(product_listing_vals,
    #                                                                                     shopify_product_listing)
    #             need_to_update_shopify_product_listing = False
    #
    #         instance.price_list_id.set_product_price(shopify_product_listing_item.product_id.id,
    #                                                  variant.get("price"))
    #     return woocommerce_product_listing

    #
    # def synchronize_variant_data_with_existing_template(self, instance, variant_data, product_data,
    #                                                     shopify_product_listing, product_listing_vals,
    #                                                     product_queue_line, log_id):
    #     """
    #     This method syncs Shopify variant data with an existing Shopify template in Odoo.
    #     """
    #     need_to_archive = False
    #     variant_ids = []
    #     shopify_attributes = product_data.get("options")
    #     odoo_product_template = shopify_product_listing.product_tmpl_id
    #     name = product_listing_vals.get("template_title", "")
    #
    #     for variant in variant_data:
    #         variant_id = variant.get("id")
    #         product_sku = variant.get("sku")
    #
    #         if not product_sku:
    #             message = "Product %s have no sku having variant id %s." % (name, variant_id)
    #             _logger.info(message)
    #             self.env['shopify.log.line'].with_context(
    #                 for_variant_line=product_queue_line).generate_shopify_process_line(
    #                 'product', 'import', instance, message,
    #                 False, False, log_id, True)
    #             if product_queue_line:
    #                 product_queue_line.state = 'failed'
    #             continue
    #
    #         # Here we are not passing SKU while searching shopify product, Because We are updating existing product.
    #         odoo_product_variant = self.env["product.product"]
    #         shopify_product_listing_item_obj = self.env["shopify.product.listing.item"]
    #
    #         shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #             [("shopify_product_variant_id", "=", variant_id), ("shopify_instance_id", "=", instance.id)], limit=1)
    #         if product_sku:
    #             if not shopify_product_listing_item:
    #                 shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #                     [("product_sku", "=", product_sku), ("shopify_product_variant_id", "=", False),
    #                      ("shopify_instance_id", "=", instance.id)], limit=1)
    #             if not shopify_product_listing_item:
    #                 shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #                     [("product_id.default_code", "=", product_sku), ("shopify_product_variant_id", "=", False),
    #                      ("shopify_instance_id", "=", instance.id)], limit=1)
    #             if not shopify_product_listing_item:
    #                 odoo_product_variant = odoo_product_variant.search([("default_code", "=", product_sku)], limit=1)
    #         if shopify_product_listing_item and not odoo_product_variant:
    #             odoo_product_variant = shopify_product_listing_item.product_id
    #
    #         product_listing_item_vals = self.prepare_product_listing_item_vals(instance, variant)
    #         domain = [("shopify_product_variant_id", "=", False), ("shopify_instance_id", "=", instance.id),
    #                   ("shopify_product_listing_id", "=", shopify_product_listing.id)]
    #         if not shopify_product_listing_item:
    #             domain.append(("product_sku", "=", product_sku))
    #             shopify_product_listing_item = shopify_product_listing_item_obj.search(domain, limit=1)
    #
    #             if not shopify_product_listing_item:
    #                 attribute_value_domain = self.retrieve_template_attribute_values(shopify_attributes,
    #                                                                                  odoo_product_template.id,
    #                                                                                  variant)
    #                 if attribute_value_domain:
    #                     odoo_product_variant = odoo_product_variant.search(attribute_value_domain)
    #
    #             if odoo_product_variant:
    #                 shopify_product_listing_item = self.create_or_update_shopify_product_listing_item(
    #                     product_listing_item_vals,
    #                     shopify_product_listing_item,
    #                     shopify_product_listing,
    #                     odoo_product_variant)
    #
    #             # If odoo's product not matched with response then need to create new product in odoo or not.
    #             elif instance.create_product_if_not_found:
    #                 if odoo_product_template.attribute_line_ids:
    #                     shopify_product_listing_item = self.sync_odoo_product_variant(odoo_product_template,
    #                                                                                   shopify_attributes,
    #                                                                                   variant, shopify_product_listing,
    #                                                                                   product_listing_item_vals)
    #                 else:
    #                     attribute_line_data = self.generate_variant_attribute_line_data(shopify_attributes, variant)
    #                     odoo_product_variant = self.shopify_create_product_without_variant(name, variant,
    #                                                                                        product_listing_vals.get(
    #                                                                                            "body_html"),
    #                                                                                        attribute_line_data)
    #
    #                     need_to_archive = True
    #                     shopify_product_listing, shopify_product_listing_item = self.create_or_update_shopify_product_listing_and_listing_item(
    #                         product_listing_vals, product_listing_item_vals, shopify_product_listing,
    #                         shopify_product_listing_item, odoo_product_variant, update_product_listing=True,
    #                         update_product_listing_item=True)
    #
    #                 if isinstance(shopify_product_listing_item, str):
    #                     message = shopify_product_listing_item
    #                     _logger.info(message)
    #                     self.env['shopify.log.line'].with_context(
    #                         for_variant_line=product_queue_line).generate_shopify_process_line('product', 'import',
    #                                                                                            instance,
    #                                                                                            message, False, False,
    #                                                                                            log_id, True)
    #                     if product_queue_line:
    #                         product_queue_line.state = 'failed'
    #                     variant_ids = []
    #                     break
    #             else:
    #                 message = "Product %s not found for SKU %s in Odoo." % (name, product_sku)
    #                 _logger.info(message)
    #                 self.env['shopify.log.line'].with_context(
    #                     for_variant_line=product_queue_line).generate_shopify_process_line('product', 'import',
    #                                                                                        instance, message,
    #                                                                                        False, False, log_id, True)
    #                 if product_queue_line:
    #                     product_queue_line.state = 'failed'
    #                 continue
    #         else:
    #             self.create_or_update_shopify_product_listing_item(product_listing_item_vals,
    #                                                                shopify_product_listing_item)
    #         instance.price_list_id.set_product_price(shopify_product_listing_item.product_id.id,
    #                                                  variant.get("price"))
    #         variant_ids.append(variant_id)
    #
    #     return variant_ids, need_to_archive
    #
    # def sync_product_with_existing_product_listing(self, shopify_product_listing, product_data, instance,
    #                                                product_category, log_id, product_queue_line):
    #     """
    #     Import existing Shopify product listing.
    #     """
    #     product_listing_vals = self.prepare_woocommerce_product_listing_vals(product_data, instance, product_category)
    #     variant_data = product_data.get("variants")
    #
    #     self.create_or_update_shopify_product_listing(product_listing_vals, shopify_product_listing)
    #
    #     variant_ids, need_to_archive = self.synchronize_variant_data_with_existing_template(instance, variant_data,
    #                                                                                         product_data,
    #                                                                                         shopify_product_listing,
    #                                                                                         product_listing_vals,
    #                                                                                         product_queue_line, log_id)
    #     if need_to_archive:
    #         products_to_archive = shopify_product_listing.shopify_product_listing_items.filtered(
    #             lambda x: int(x.shopify_product_variant_id) not in variant_ids)
    #         products_to_archive.write({"active": False})
    #     return shopify_product_listing if variant_ids else False

    # def woocommerce_create_products(self, product_queue_line, instance, log_id, order_line_product_listing_id=False):
    #     """
    #     This method is used to create or update Woocommerce product listing, listing item & also Odoo's product &
    #     product variants.
    #     :param: order_line_product_listing_id: This parameter is used when import order process running & at that time product not found in Odoo based on product id.
    #     """
    #     if order_line_product_listing_id:
    #         try:
    #             api_url = "{0}/wp-json/wc/v3/products/{1}".format(instance.woocommerce_url,
    #                                                               order_line_product_listing_id)
    #             response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("GET", api_url)
    #             if response_status:
    #                 product_data = response_data
    #         except Exception as e:
    #             raise ValidationError(e)
    #     else:
    #         product_data = eval(product_queue_line.product_data_to_process)
    #
    #     if not product_data:
    #         return True
    #
    #     # Product category find & if not match then create new one.
    #     product_category = self.get_odoo_product_category(product_data.get('categories')[0].get('name'))
    #     woocommerce_product_listing = self.search(
    #         [("woocommerce_product_id", "=", product_data.get("id")), ("woocommerce_instance_id", "=", instance.id),
    #          ("woocommerce_default_code", "=", product_data.get("sku")),
    #          ])
    #
    #     if not woocommerce_product_listing:
    #         woocommerce_product_listing = self.create_new_product_listing(product_data, instance, product_category,
    #                                                                       log_id,
    #                                                                       product_queue_line)
    #     else:
    #         woocommerce_product_listing = self.sync_product_with_existing_product_listing(woocommerce_product_listing,
    #                                                                                       product_data, instance,
    #                                                                                       product_category, log_id,
    #                                                                                       product_queue_line)
    #     # Image sync process
    #     # if woocommerce_product_listing and instance.is_sync_images:
    #     #     self.sync_product_image_from_shopify(instance, woocommerce_product_listing, product_data)
    #     #
    #     if product_queue_line and woocommerce_product_listing and not woocommerce_product_listing.product_data_queue_id:
    #         woocommerce_product_listing.product_data_queue_id = product_queue_line.woocommerce_product_queue_id
    #
    #     # if woocommerce_product_listing and product_queue_line:
    #     #     product_queue_line.state = "completed"
    #     #     msg = "Product => {} is successfully imported in odoo.".format(woocommerce_product_listing.name)
    #     #     _logger.info(msg)
    #     #     self.env['shopify.log.line'].with_context(
    #     #         for_variant_line=product_queue_line).generate_shopify_process_line('product', 'import', instance, msg,
    #     #                                                                            False,
    #     #                                                                            product_data, log_id, False)
    #     #     self._cr.commit()
    #     return woocommerce_product_listing
    def create_or_update_product_listing_items(self, product_data, product_listing, instance, product_queue_line,
                                               log_id, api_url):
        """Fetch WooCommerce variations and create/update product listing items."""

        product_listing_item_obj = self.env['woocommerce.product.listing.item']

        # Call WooCommerce Variants API
        if api_url:
            variant_api_url = api_url
        else:
            variant_api_url = "{0}/wp-json/wc/v3/products/{1}/variations".format(
                instance.woocommerce_url,
                product_data.get('id')
            )
        params = "per_page=100"
        response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("GET",
                                                                                                  variant_api_url,
                                                                                                  False, params)
        if not response_status or not isinstance(response_data, list):
            return
        for wc_variant in response_data:
            wc_variant_id = wc_variant.get('id')
            wc_sku = wc_variant.get('sku') or False
            wc_price = wc_variant.get('price') or 0.0
            if not wc_sku:
                message = "Product %s have no sku having variant id %s." % (wc_variant.get('name'), wc_variant_id)
                _logger.info(message)
                self.env['woocommerce.log.line'].with_context(
                    for_variant_line=product_queue_line).generate_woocommerce_process_line('product', 'import',
                                                                                           instance,
                                                                                           message, False, False,
                                                                                           log_id,
                                                                                           True)
                if product_queue_line:
                    product_queue_line.state = 'failed'
                continue
            listing_item = product_listing_item_obj.search([
                ('woocommerce_product_variant_id', '=', wc_variant_id),
                ('woocommerce_product_listing_id', '=', product_listing.id)
            ], limit=1)

            vals = {
                'woocommerce_product_listing_id': product_listing.id,
                'woocommerce_product_variant_id': wc_variant_id,
                'name': wc_variant.get('name'),
                'product_sku': wc_sku,
                'woocommerce_instance_id': instance.id,
                'product_id': False,
                'exported_in_woocommerce': True
            }
            if listing_item:
                listing_item.write(vals)
            else:
                product_listing_item_obj.create(vals)
        if next_page_link:
            self.create_or_update_product_listing_items(
                product_data, product_listing, instance, product_queue_line, log_id, api_url=next_page_link
            )
        return response_status, response_data

    def sync_product_image_from_woocommerce(self, instance, product_listing,product_data):
        """
        Sync WooCommerce product & variant images into Odoo.
        - Store in custom image model
        - Update product template and product.product images
        """
        woocommerce_image_model = self.env['woocommerce.product.image']
        listing_item_model = self.env['woocommerce.product.listing.item']

        # ============ STEP 1: SYNC MAIN PRODUCT IMAGES ============
        for image in product_data.get('images', []):
            image_url = image.get('src')
            if not image_url:
                continue

            wc_image_id = image.get('id')
            image_datas = base64.b64encode(
                requests.get(image_url, verify=False, timeout=30).content
            )

            listing_image_id = woocommerce_image_model.search(
                [('woocommerce_image_id', '=', wc_image_id)], limit=1
            )
            vals = {
                'name': product_listing.name,
                'woocommerce_image_id': wc_image_id,
                'sequence': image.get('position'),
                'image': image_datas,
                'woocommerce_listing_id': product_listing.id,
                'listing_item_ids': [(6, 0, [])],  # no variants for template image
            }

            if listing_image_id:
                listing_image_id.write(vals)
            else:
                woocommerce_image_model.create(vals)

            # Set first image as product template image
            if image.get('position') == 1:
                product_listing.product_tmpl_id.write({'image_1920': image_datas})

        # ============ STEP 2: FETCH VARIANTS ============
        variant_response_data = self.fetch_woocommerce_variants(
            instance, product_data, listing_item_model
        )

        # ============ STEP 3: SYNC VARIANT IMAGES ============
        for variant in variant_response_data:
            variant_id = variant.get('id')
            variant_images = variant.get('image') and [variant['image']] or variant.get('images', [])

            if not variant_images:
                continue

            # Find corresponding listing item (mapped to product.product)
            listing_item = listing_item_model.search([
                ('woocommerce_instance_id', '=', instance.id),
                ('woocommerce_product_listing_id', '=', variant_id)
            ], limit=1)

            for image in variant_images:
                image_url = image.get('src')
                if not image_url:
                    continue

                wc_image_id = image.get('id')
                image_datas = base64.b64encode(
                    requests.get(image_url, verify=False, timeout=30).content
                )

                listing_image_id = woocommerce_image_model.search(
                    [('woocommerce_image_id', '=', wc_image_id)], limit=1
                )
                vals = {
                    'name': product_listing.name,
                    'woocommerce_image_id': wc_image_id,
                    'sequence': image.get('position'),
                    'image': image_datas,
                    'woocommerce_listing_id': product_listing.id,
                    'listing_item_ids': [(6, 0, listing_item.ids)],
                }

                if listing_image_id:
                    listing_image_id.write(vals)
                else:
                    woocommerce_image_model.create(vals)

                # Update variant product image
                if listing_item and listing_item.product_id:
                    listing_item.product_id.write({'image_1920': image_datas})

        return True
    def woocommerce_create_products(self, product_queue_line, instance, log_id, order_line_product_listing_id=False):
        """
        Main entry point to create/update WooCommerce products in Odoo.
        """
        # Step 1: Get Product Data
        product_data = self.get_woocommerce_product_data(instance, product_queue_line, order_line_product_listing_id)
        if not product_data:
            return True

        # Step 2: Find/Create Product Listing and listing item
        product_category = self.get_odoo_product_category(
            product_data.get('categories')[0].get('name') if product_data.get('categories') else "Uncategorized"
        )
        woocommerce_product_listing = self.create_or_update_product_listing(product_data, product_category, instance,
                                                                            product_queue_line)
        product_variant_response_status, product_variant_response_data = self.create_or_update_product_listing_items(
            product_data, woocommerce_product_listing, instance, product_queue_line, log_id, api_url=False)

        # Step 3: Find/Create Product Template
        product_template = False
        if product_variant_response_status and instance.woocommerce_create_product_if_not_found:
            product_template = self.create_or_update_product_template(product_data, product_category, instance,
                                                                      product_variant_response_data)
            if product_template:
                woocommerce_product_listing.product_tmpl_id = product_template.id
            # # Step 4: Handle Variable Products
            if product_data.get('type') == 'variable':
                self.sync_variable_product(product_data, product_template, woocommerce_product_listing, instance,
                                           log_id, product_queue_line)
            # Image sync process
            if woocommerce_product_listing and instance.is_sync_wc_images:
                self.sync_product_image_from_woocommerce(instance, woocommerce_product_listing, product_data)
        if product_queue_line and woocommerce_product_listing and not woocommerce_product_listing.product_data_queue_id:
            woocommerce_product_listing.product_data_queue_id = product_queue_line.woocommerce_product_queue_id
        # Step 5: Mark Queue Completed

        self.log_and_finalize_queue(product_queue_line, instance, woocommerce_product_listing, product_template,
                                    product_data, log_id)

        return woocommerce_product_listing

    # ---------------------------
    # Helper Methods
    # ---------------------------

    def get_woocommerce_product_data(self, instance, product_queue_line, product_listing_id=False):
        """
        Fetch product data either from queue or directly from WooCommerce API.
        """
        try:
            if product_listing_id:
                api_url = f"{instance.woocommerce_url}/wp-json/wc/v3/products/{product_listing_id}"
                response_status, response_data, next_page_link = instance.woocommerce_api_calling_process("GET", api_url)
                return response_data if response_status else False
            return eval(product_queue_line.product_data_to_process)
        except Exception as e:
            raise ValidationError(f"Failed to fetch WooCommerce product data: {e}")

    def create_or_update_product_listing(self, product_data, product_category, instance, product_queue_line=False):
        """
        Create or update woocommerce product listing, and link the product template
        only if create_product_if_not_found is True or template already exists.
        """
        listing = self.search([('woocommerce_product_id', '=', product_data.get("id"))], limit=1)

        # ✅ Ensure queue line is valid
        if product_queue_line and not product_queue_line.exists():
            product_queue_line = False

        woocommerce_tag_obj = self.env["woocommerce.product.tags"]
        tag_ids = []
        sequence = 0

        def convert_date(key):
            return self.convert_woocommerce_date_into_odoo_date_format(product_data.get(key))

        # website_published = "unpublished"
        # if product_data.get('status'):
        #     website_published = product_data.get("status")

        if product_data.get("tags"):
            for tag in product_data.get("tags"):
                tags_id = tag.get('id')
                tags_name = tag.get('name')
                slug = tag.get('slug')
                woocommerce_tag = woocommerce_tag_obj.search([("name", "=", tags_name)], limit=1)
                if not woocommerce_tag:
                    sequence += 1
                    woocommerce_tag = self.env['woocommerce.product.tags'].create({'name': tag, 'code': tags_id, 'instance_id': instance.id,
                                 'company_id': instance.company_id.id, 'slug': slug,"sequence":sequence})
                sequence = woocommerce_tag.sequence if woocommerce_tag else 0
                tag_ids.append(woocommerce_tag.id)

        product_listing_vals = {
            "name": product_data.get("name"),
            "description": product_data.get("description"),
            "woocommerce_product_id": product_data.get("id"),
            "woocommerce_instance_id": instance.id,
            "product_catg_id": product_category.id,
            "exported_in_woocommerce": True,
            "woocommerce_default_code": product_data.get('sku'),
            "tag_ids":tag_ids
        }
        if not listing:
            listing = self.create(product_listing_vals)
        else:
            listing.write(product_listing_vals)
        return listing

    def create_or_update_product_template(self, product_data, product_category, instance,
                                          product_variant_response_data):
        """
        Find or create product.template for WooCommerce product.
        Priority:
          1) Search variant SKU in product.product → reuse its template
          2) Else search product.template by variant SKU
          3) Else create new template with first variant SKU
        """
        product_template_obj = self.env['product.template']
        product_product_obj = self.env['product.product']

        # --- Step 0: Get first available variant SKU ---
        product_variant_sku = False
        for product_variant in product_variant_response_data or []:
            if product_variant.get("sku"):
                product_variant_sku = product_variant.get("sku")
                if product_variant_sku:
                    product_variant = product_product_obj.search([('default_code', '=', product_variant_sku)], limit=1)
                    product_variant_sku = product_variant.default_code
                break  # only first valid SKU

        if not product_variant_sku:
            # fallback: if no SKU in variant response, use main product_data SKU
            product_variant_sku = product_data.get("sku")

        # --- Step 1: Search in product.product (variant level) ---
        variant = False
        if product_variant_sku:
            variant = product_product_obj.search([('default_code', '=', product_variant_sku)], limit=1)

        if variant:
            template = variant.product_tmpl_id
            template.write({
                'name': product_data.get('name'),
                'type': 'product',
                'categ_id': product_category.id,
            })
            return template

        # --- Step 2: Search in product.template directly ---
        template = False
        if product_variant_sku:
            template = product_template_obj.search([('default_code', '=', product_data.get('sku'))], limit=1)
        if not template:
            template = product_template_obj.search([('name', '=', product_data.get('name'))], limit=1)
        if template:
            template.write({
                'name': product_data.get('name'),
                'type': 'product',
                'categ_id': product_category.id,
                'default_code': product_data.get('sku'),
            })
            return template

        # --- Step 3: Create new template ---
        vals = {
            'name': product_data.get('name'),
            'type': 'product',
            'categ_id': product_category.id,
            'default_code': product_data.get('sku'),
        }
        template = product_template_obj.create(vals)
        return template

    def sync_template_attributes(self, product_data, product_template):
        """
        Sync attributes from WooCommerce to the Odoo product template.
        Returns the mapping of attribute names to value ids.
        """
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']
        product_template_attribute_line_obj = self.env['product.template.attribute.line']

        attribute_value_map = {}

        for attribute in product_data.get('attributes', []):
            attr_name = attribute.get('name')
            attr_values = attribute.get('options', [])
            if not attr_name or not attr_values:
                continue

            product_attribute = product_attribute_obj.search([('name', '=', attr_name)], limit=1)
            if not product_attribute:
                product_attribute = product_attribute_obj.create({'name': attr_name})

            value_ids = []
            for val_name in attr_values:
                value = product_attribute_value_obj.search([
                    ('name', '=', val_name),
                    ('attribute_id', '=', product_attribute.id)
                ], limit=1)
                if not value:
                    value = product_attribute_value_obj.create({
                        'name': val_name,
                        'attribute_id': product_attribute.id
                    })
                value_ids.append(value.id)

            # Update or create template attribute line
            line = product_template_attribute_line_obj.search([
                ('product_tmpl_id', '=', product_template.id),
                ('attribute_id', '=', product_attribute.id)
            ], limit=1)

            if line:
                for val_id in value_ids:
                    if val_id not in line.value_ids.ids:
                        line.write({'value_ids': [(4, val_id)]})
            else:
                product_template_attribute_line_obj.create({
                    'product_tmpl_id': product_template.id,
                    'attribute_id': product_attribute.id,
                    'value_ids': [(6, 0, value_ids)]
                })

            attribute_value_map[attr_name] = value_ids

        return attribute_value_map

    def fetch_woocommerce_variants(self, instance, product_data, product_listing_item_obj):
        """
        Fetch all variants for a WooCommerce product via API.
        Returns a list of variant dicts.
        """
        product_variant_response_data = []
        variant_api_url = "{0}/wp-json/wc/v3/products/{1}/variations".format(
            instance.woocommerce_url,
            product_data.get('id')
        )

        while variant_api_url:
            params = "per_page=100"
            response_status, response_data, next_page_link =instance.woocommerce_api_calling_process("GET", variant_api_url,False,params)
            if not response_status or not response_data:
                break
            product_variant_response_data.extend(response_data)  # to avoid list of list we use extend not append
            variant_api_url = next_page_link

        _logger.info("Product Variant Response Data List ::: {}".format(product_variant_response_data))
        return product_variant_response_data

    def process_woocommerce_variant(self, variation, product_template, product_listing, instance, log_id,
                                    product_queue_line):
        """
        Create or update a variant in Odoo based on WooCommerce variant data,
        and update product listing item & price.
        """
        product_attribute_obj = self.env['product.attribute']
        product_attribute_value_obj = self.env['product.attribute.value']
        product_template_attribute_line_obj = self.env['product.template.attribute.line']
        product_template_attribute_value_obj = self.env['product.template.attribute.value']
        product_product_obj = self.env['product.product']
        product_listing_item_obj = self.env['woocommerce.product.listing.item']

        sku = str(variation.get('sku') or '').strip()
        variant_id = variation.get('id')
        if not sku:
            message = f"Product {variation.get('name')} has no SKU (variant id {variant_id})"
            _logger.info(message)
            self.env['shopify.log.line'].with_context(
                for_variant_line=product_queue_line
            ).generate_shopify_process_line('product', 'import', instance, message, False, False, log_id, True)
            return

        price = float(variation.get('price') or 0.0)
        combination_values = []

        for attr in variation.get('attributes', []):
            attr_name = attr.get('name')
            attr_value = attr.get('option')
            if not attr_name or not attr_value:
                continue

            product_attribute = product_attribute_obj.search([('name', '=', attr_name)], limit=1)
            if not product_attribute:
                product_attribute = product_attribute_obj.create({'name': attr_name})

            value = product_attribute_value_obj.search([
                ('name', '=', attr_value),
                ('attribute_id', '=', product_attribute.id)
            ], limit=1)
            if not value:
                value = product_attribute_value_obj.create({
                    'name': attr_value,
                    'attribute_id': product_attribute.id
                })

            line = product_template_attribute_line_obj.search([
                ('product_tmpl_id', '=', product_template.id),
                ('attribute_id', '=', product_attribute.id)
            ], limit=1)
            if line and value.id not in line.value_ids.ids:
                line.write({'value_ids': [(4, value.id)]})
            elif not line:
                product_template_attribute_line_obj.create({
                    'product_tmpl_id': product_template.id,
                    'attribute_id': product_attribute.id,
                    'value_ids': [(6, 0, [value.id])]
                })

            ptav = product_template_attribute_value_obj.search([
                ('product_tmpl_id', '=', product_template.id),
                ('attribute_id', '=', product_attribute.id),
                ('product_attribute_value_id', '=', value.id)
            ], limit=1)
            if ptav:
                combination_values.append(ptav.id)

        # Sort to ensure consistent ordering for comparison
        combination_values = sorted(combination_values)

        # Find or create variant
        domain = [('product_tmpl_id', '=', product_template.id)]
        for ptav_id in combination_values:
            domain.append(('product_template_attribute_value_ids', 'in', [ptav_id]))

        variant = product_product_obj.search(domain, limit=1)
        if variant:
            variant.write({'default_code': sku})
        elif combination_values:
            variant = product_product_obj.create({
                'product_tmpl_id': product_template.id,
                'product_template_attribute_value_ids': [(6, 0, combination_values)],
                'default_code': sku,
            })

        # Update listing item and price
        if product_listing and variant:
            listing_item = product_listing_item_obj.search([
                ('woocommerce_product_listing_id', '=', product_listing.id),
                ('woocommerce_product_variant_id', '=', variant_id)
            ], limit=1)

            if listing_item:
                listing_item.write({
                    'product_id': variant.id,
                    'product_sku': sku,
                })

            # Always set price in Woo price list
            instance.woocommerce_price_list_id.set_woocommerce_product_price(
                variant.id, price
            )
        else:
            _logger.warning(f"[Woo] Variant with SKU '{sku}' could not be matched or created.")

    def sync_variable_product(self, product_data, product_template, product_listing, instance, log_id,
                              product_queue_line):
        if product_listing and not product_listing.product_tmpl_id:
            product_listing.product_tmpl_id = product_template.id

        # Using below method we can set or update attributes
        self.sync_template_attributes(product_data, product_template)

        # using this method for safety purpose we create all product variant automatically - odoo base method
        product_template._create_variant_ids()
        product_variant_response_data = self.fetch_woocommerce_variants(instance, product_data,
                                                                        self.env['woocommerce.product.listing.item'])

        for variation in product_variant_response_data:
            self.process_woocommerce_variant(variation, product_template, product_listing, instance, log_id,
                                             product_queue_line)

    def log_and_finalize_queue(self, product_queue_line, instance, product_listing, product_template, product_data,
                               log_id):
        """
        Mark queue line as complete and log success message.
        """
        if product_queue_line:
            product_queue_line.state = "completed"
            msg = f"Product => {product_listing.name} imported successfully with template {product_template.name if product_template else ''}"
            self.env['woocommerce.log.line'].with_context(
                for_variant_line=product_queue_line).generate_woocommerce_process_line(
                'product', 'import', instance, msg, False, product_data, log_id, False
            )
            self._cr.commit()

    #
    # def create_or_update_shopify_listing_from_odoo_product_tmpl(self, shopify_instance, product_template,
    #                                                        shopify_template_id):
    #     """
    #     This method is used to create or update the shopify product in instance.
    #     @return: shopify_product_listing, shopify_template_id
    #     """
    #
    #     shopify_product_listing = self.search([
    #         ("shopify_instance_id", "=", shopify_instance.id),
    #         ("product_tmpl_id", "=", product_template.id)], limit=1)
    #
    #     # prepare a template Vals for export product
    #     shopify_product_template_vals = {"product_tmpl_id": product_template.id,
    #                                      "shopify_instance_id": shopify_instance.id,
    #                                      "product_catg_id": product_template.categ_id.id,
    #                                      "name": product_template.name}
    #     if not shopify_product_listing:
    #         shopify_product_listing = self.create(shopify_product_template_vals)
    #         shopify_template_id = shopify_product_listing.id
    #     else:
    #         if shopify_template_id != shopify_product_listing.id:
    #             shopify_product_listing.write(shopify_product_template_vals)
    #             shopify_template_id = shopify_product_listing.id
    #     if shopify_product_listing not in self:
    #         self += shopify_product_listing
    #
    #     return shopify_product_listing, shopify_template_id
    #
    # def prepare_shopify_product_listing_for_update_and_export(self, new_product, shopify_product_listing_id, instance,
    #                                                           is_publish, is_set_price, log_id):
    #     """
    #     This method will be used for both Export and Updating product listing in Shopify.
    #     """
    #     if instance or is_publish:
    #         published_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    #         if is_publish == "unpublish_product":
    #             new_product.published_at = None
    #             new_product.published_scope = "null"
    #         elif is_publish == "publish_product_global":
    #             new_product.published_scope = "global"
    #             new_product.published_at = published_at
    #         else:
    #             new_product.published_scope = "publish_product_web"
    #             new_product.published_at = published_at
    #
    #         if shopify_product_listing_id.description:
    #             new_product.body_html = shopify_product_listing_id.description
    #         if shopify_product_listing_id.product_tmpl_id.seller_ids:
    #             new_product.vendor = shopify_product_listing_id.product_tmpl_id.seller_ids[0].display_name
    #         new_product.product_type = shopify_product_listing_id.product_catg_id.name
    #         new_product.title = shopify_product_listing_id.name
    #
    #         shopify_product_listing_items = []
    #         for shopify_product_listing_item in shopify_product_listing_id.shopify_product_listing_items:
    #             product_listing_items_vals = self.env[
    #                 "shopify.product.listing.item"].shopify_prepare_product_listing_items_vals(instance,
    #                                                                                            shopify_product_listing_item,
    #                                                                                            is_set_price)
    #             shopify_product_listing_items.append(product_listing_items_vals)
    #             # Getting an Error While update product from odoo to shopify because below id not available in shopify
    #         new_product.variants = shopify_product_listing_items
    #         # used to set product attribute vals while export/update products from Odoo to Shopify store.
    #         if shopify_product_listing_id.product_tmpl_id.attribute_line_ids:
    #             attribute_list = []
    #             attribute_position = 1
    #             product_attribute_line_obj = self.env["product.template.attribute.line"]
    #             product_attribute_lines = product_attribute_line_obj.search(
    #                 [("id", "in", shopify_product_listing_id.product_tmpl_id.attribute_line_ids.ids)],
    #                 order="attribute_id")
    #             for attribute_line in product_attribute_lines.filtered(
    #                     lambda x: x.attribute_id.create_variant == "always"):
    #                 info = {}
    #                 attribute = attribute_line.attribute_id
    #                 value_names = []
    #                 for value in attribute_line.value_ids:
    #                     value_names.append(value.name)
    #                 info.update({"name": attribute.name, "values": value_names,
    #                              "position": attribute_position})
    #                 attribute_list.append(info)
    #                 attribute_position = attribute_position + 1
    #             new_product.options = attribute_list
    #     return True
    #
    # def update_products_listing_item_details_shopify_information(self, new_product, shopify_product_listing_id,
    #                                                              shopify_is_publish, instance, log_id):
    #     """
    #     this method is used to update the shopify product listing id, created date, update date,
    #     public date in shopify information
    #     :param new_product: shopify store product
    #     :param shopify_product_listing_id: shopify product listing
    #     :param is_publish: if true then update public date of shopify product
    #     """
    #     result_dict = new_product.to_dict()
    #     created_at = datetime.now()
    #     updated_at = datetime.now()
    #     shopify_product_id = result_dict.get("id")
    #     product_listing_vals = {"create_date": created_at, "write_date": updated_at,
    #                             "shopify_product_id": shopify_product_id,
    #                             "exported_in_shopify": True,
    #                             }
    #     if shopify_is_publish == "unpublish_product":
    #         shopify_product_listing_id.write({"published_at": False, "website_published": "unpublished"})
    #     elif shopify_is_publish == 'publish_product_global':
    #         shopify_product_listing_id.write({'published_at': updated_at, 'website_published': 'published_global'})
    #     else:
    #         shopify_product_listing_id.write({'published_at': updated_at, 'website_published': 'published_web'})
    #     if not shopify_product_listing_id.exported_in_shopify:
    #         shopify_product_listing_id.write(product_listing_vals)
    #         message = 'Export product To Shopify : {}'.format(shopify_product_listing_id.name)
    #         self.env['shopify.log.line'].generate_shopify_process_line('product', 'export', instance, message,
    #                                                                    False, False, log_id, False)
    #     # used to write the variation response values in the Shopify variant.
    #     for variant_dict in result_dict.get("variants"):
    #         updated_at = datetime.now()
    #         created_at = datetime.now()
    #         inventory_item_id = variant_dict.get("inventory_item_id") or False
    #         variant_id = variant_dict.get("id")
    #         message = 'Product Variate ID : {}'.format(variant_id)
    #         self.env['shopify.log.line'].generate_shopify_process_line('product', 'export', instance, message,
    #                                                                    False, message, log_id, False)
    #         # Searches for Shopify/Odoo product with SKU.
    #         shopify_product_listing_item_obj = self.env["shopify.product.listing.item"]
    #         product_sku = variant_dict.get("sku")
    #         instance = shopify_product_listing_id.shopify_instance_id
    #
    #         shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #             [("shopify_product_variant_id", "=", variant_id), ("shopify_instance_id", "=", instance.id)], limit=1)
    #         if product_sku:
    #             if not shopify_product_listing_item:
    #                 shopify_product_listing_item = shopify_product_listing_item_obj.search(
    #                     [("product_id.default_code", "=", product_sku), ("shopify_product_variant_id", "=", False),
    #                      ("shopify_instance_id", "=", instance.id)], limit=1)
    #
    #         if shopify_product_listing_item and not shopify_product_listing_item.exported_in_shopify:
    #             shopify_product_listing_item.write({
    #                 "shopify_product_variant_id": variant_id,
    #                 "write_date": updated_at,
    #                 "create_date": created_at,
    #                 "inventory_item_id": inventory_item_id,
    #                 "exported_in_shopify": True
    #             })
    #     return True
    #
    # def update_products_details_in_shopify_store(self, instance_id, shopify_products_listing, shopify_is_set_price,
    #                                              shopify_is_publish, log_id):
    #     """
    #            This method is used to Update product in shopify store.
    #            :param instance_id: shopify instance id.
    #            :param shopify_is_set_price: if true then update price in shopify store.
    #            :param shopify_is_publish: if true then update image in shopify store.
    #            :param shopify_is_set_image: if true then publish product in shopify web.
    #            :param shopify_templates: Record of shopify templates.
    #     """
    #     instance_id.connect_in_shopify()
    #     for shopify_product_listing_id in shopify_products_listing:
    #         if not shopify_product_listing_id.shopify_product_id:
    #             continue
    #         try:
    #             shopify_product = shopify.Product().find(shopify_product_listing_id.shopify_product_id)
    #             message = 'Shopify Product ID : {}'.format(shopify_product.id)
    #             self.env['shopify.log.line'].generate_shopify_process_line('product', 'update', instance_id,
    #                                                                        message,
    #                                                                        False, message, log_id, False)
    #         except ResourceNotFound:
    #             error_msg = ("Error while trying to find Shopify Product {}".format(
    #                 shopify_product_listing_id.shopify_product_listing_id))
    #             self.env['shopify.log.line'].generate_shopify_process_line('product', 'update', instance_id, error_msg,
    #                                                                        False, False, log_id, True)
    #             continue
    #         except Exception as e:
    #             error_msg = ("Error while trying to find Shopify Product {} ERROR:{}".format(
    #                 shopify_product_listing_id.shopify_product_listing_items and shopify_product_listing_id.shopify_product_listing_items.shopify_product_listing_id.name,
    #                 e))
    #             self.env['shopify.log.line'].generate_shopify_process_line('product', 'update', instance_id, error_msg,
    #                                                                        False, False, log_id, True)
    #             raise AccessError(
    #                 _("Error while trying to find Shopify Product {} ERROR:{}".format(
    #                     shopify_product_listing_id.shopify_product_listing_items and shopify_product_listing_id.shopify_product_listing_items.shopify_product_listing_id.name,
    #                     e)))
    #         if not shopify_product:
    #             error_msg = ("Shopify Product Not Found : {}".format(
    #                 shopify_product_listing_id.shopify_product_listing_items and shopify_product_listing_id.shopify_product_listing_items.shopify_product_listing_id.name))
    #             self.env['shopify.log.line'].generate_shopify_process_line('product', 'update', instance_id, error_msg,
    #                                                                        False, False, log_id, True)
    #             continue
    #         self.prepare_shopify_product_listing_for_update_and_export(shopify_product, shopify_product_listing_id,
    #                                                                    instance_id,
    #                                                                    shopify_is_publish, shopify_is_set_price, log_id)
    #         result = shopify_product.save()
    #         if result:
    #             message = 'Shopify Product ID : {}'.format(shopify_product.id)
    #             self.env['shopify.log.line'].generate_shopify_process_line('product', 'update', instance_id,
    #                                                                        message,
    #                                                                        False, message, log_id, False)
    #             self.update_products_listing_item_details_shopify_information(shopify_product,
    #                                                                           shopify_product_listing_id,
    #                                                                           shopify_is_publish, instance_id, log_id)
    #
    #         updated_at = datetime.now()
    #         shopify_product_listing_id.write({"write_date": updated_at})
    #         shopify_product_listing_id.shopify_product_listing_items.write({"write_date": updated_at})
    #
    #         return True
    #
    # def unlink(self):
    #     if self.shopify_product_listing_items:
    #         self.shopify_product_listing_items.unlink()
    #     return super(ShopifyProductListing, self).unlink()


class ProductCategory(models.Model):
    _inherit = "product.category"
    _description = "Product Category"

    woocommerce_product_cat = fields.Boolean(string="Woocommerce Product Category?",
                                             help="if True it means it is a Woocommerce category", default=False)
