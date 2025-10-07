import logging
import requests
import json
from odoo.tools.safe_eval import safe_eval
from odoo import models, fields, tools, api

_logger = logging.getLogger("WooCommerce Inventory Queue")


class InventoryDataQueue(models.Model):
    _name = "woocommerce.inventory.data.queue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "WooCommerce Inventory Data Queue"
    _order = 'id DESC'

    @api.depends('woocommerce_inventory_queue_line_ids.state')
    def _compute_queue_line_state_and_count(self):
        """
        Compute method to set queue state automatically based on queue line states.
        """
        for queue in self:
            queue_line_ids = queue.woocommerce_inventory_queue_line_ids
            if all(line.state == 'draft' for line in queue_line_ids):
                queue.state = 'draft'
            elif all(line.state == 'failed' for line in queue_line_ids):
                queue.state = 'failed'
            elif all(line.state == 'completed' for line in queue_line_ids):
                queue.state = 'completed'
            else:
                queue.state = 'partially_completed'

    name = fields.Char(string='Name')
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('partially_completed', 'Partially Completed'),
                   ('completed', 'Completed'), ('failed', 'Failed')],
        tracking=True, default='draft', compute="_compute_queue_line_state_and_count"
    )
    woocommerce_inventory_queue_line_ids = fields.One2many(
        "woocommerce.inventory.data.queue.line",
        "woocommerce_inventory_queue_id",
        "Inventory Queue Lines"
    )
    woocommerce_log_id = fields.Many2one('woocommerce.log', string="Logs")

    @api.model_create_multi
    def create(self, vals_list):
        """
        Add sequence number when creating a new queue record.
        """
        sequence = self.env.ref("vraja_woocommerce_odoo_integration.seq_inventory_queue")
        for vals in vals_list:
            name = sequence and sequence.next_by_id() or '/'
            if isinstance(vals, dict):
                vals.update({'name': name})
        return super(InventoryDataQueue, self).create(vals_list)

    def unlink(self):
        """
        Unlink queue lines when deleting the main queue.
        """
        for queue in self:
            if queue.woocommerce_inventory_queue_line_ids:
                queue.woocommerce_inventory_queue_line_ids.unlink()
        return super(InventoryDataQueue, self).unlink()

    def generate_woocommerce_inventory_queue(self, instance):
        """
        Create a new queue record for WooCommerce inventory updates.
        """
        return self.create({'instance_id': instance.id})

    def create_woocommerce_inventory_queue_job(self, instance_id, woocommerce_inventory_list, log_id):
        """
        Create queue and queue lines for WooCommerce stock export based on batch size.
        """
        queue_id_list = []
        batch_size = 50
        for woocommerce_inventories in tools.split_every(batch_size, woocommerce_inventory_list):
            queue_id = self.generate_woocommerce_inventory_queue(instance_id)
            for inventory in woocommerce_inventories:
                self.env['woocommerce.inventory.data.queue.line'].create_woocommerce_inventory_queue_line(
                    inventory, instance_id, queue_id, log_id
                )
            queue_id_list.append(queue_id.id)
            if not queue_id.woocommerce_inventory_queue_line_ids:
                queue_id.unlink()
        return queue_id_list

    def process_queue_to_export_stock(self):
        """
        Button action: export inventory from Odoo to WooCommerce.
        """
        self.export_inventory_from_odoo_to_woocommerce()

    from odoo.tools.safe_eval import safe_eval
    import json
    import logging

    _logger = logging.getLogger("WooCommerce Inventory Export")

    def export_inventory_from_odoo_to_woocommerce(self):
        """
        Export inventory from Odoo to WooCommerce using batch API.
        Supports both simple products and variants based on product_type in queue line.
        """
        if self._context.get('from_cron'):
            process_records = self.search([('state', 'not in', ['completed', 'failed'])])
        else:
            process_records = self

        if not process_records:
            return True

        for rec in process_records:
            log_id = rec.woocommerce_log_id or self.env['woocommerce.log'].generate_woocommerce_logs(
                'inventory', 'export', rec.instance_id, 'Process Started'
            )

            # Get queue lines to process
            if self._context.get('from_cron'):
                queue_lines = rec.woocommerce_inventory_queue_line_ids.filtered(lambda l: l.state == 'draft')
            else:
                queue_lines = rec.woocommerce_inventory_queue_line_ids.filtered(
                    lambda l: l.state in ['draft', 'failed'] and l.number_of_fails < 3
                )

            if not queue_lines:
                continue

            # Separate data for simple & variant products
            product_updates_simple = []
            variant_updates_map = {}  # {parent_product_id: [updates]}
            line_map = {}

            for line in queue_lines:
                try:
                    inventory_data = line.inventory_data_to_process
                    if isinstance(inventory_data, str):
                        inventory_data = json.loads(inventory_data)  # better: use safe_eval

                    woocommerce_id = inventory_data.get('woocommerce_product_id')
                    available_qty = int(inventory_data.get('available', 0))
                    product_type = inventory_data.get('product_type')
                    parent_product_id = inventory_data.get('parent_product_id')

                    if not woocommerce_id:
                        line.state = 'failed'
                        line.number_of_fails += 1
                        msg = f"Missing WooCommerce ID for product {line.product_id.display_name}"
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'inventory', 'export', rec.instance_id, msg, False, msg, log_id, True
                        )
                        continue

                    update_data = {
                        "id": woocommerce_id,
                        "stock_quantity": available_qty,
                        "manage_stock": True,
                        "stock_status": "instock" if available_qty > 0 else "outofstock"
                    }

                    # 🟢 Separate simple vs variant
                    if product_type == 'variant' and parent_product_id:
                        variant_updates_map.setdefault(parent_product_id, []).append(update_data)
                    else:
                        product_updates_simple.append(update_data)

                    line_map[woocommerce_id] = line

                except Exception as error:
                    line.state = 'failed'
                    line.number_of_fails += 1
                    msg = f"Error preparing stock for {line.product_id.display_name}: {str(error)}"
                    self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                        'inventory', 'export', rec.instance_id, msg, False, msg, log_id, True
                    )
                    _logger.error(msg)

            # === 🟢 Update SIMPLE products ===
            if product_updates_simple:
                try:
                    api_url = f"{rec.instance_id.woocommerce_url}/wp-json/wc/v3/products/batch"
                    request_data = {"update": product_updates_simple}
                    success, response, next_page_link = rec.instance_id.woocommerce_api_calling_process(
                        request_type='POST', api_url=api_url, request_data=json.dumps(request_data)
                    )

                    if success:
                        for prod in product_updates_simple:
                            line = line_map.get(prod.get('id'))
                            if line:
                                line.state = 'completed'
                        msg = f"✅ Updated {len(product_updates_simple)} simple products successfully."
                        rec.state = 'completed'
                        _logger.info(msg)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'inventory', 'export', rec.instance_id, msg, product_updates_simple,
                            json.dumps(response), log_id, False
                        )
                    else:
                        for prod in product_updates_simple:
                            line = line_map.get(prod.get('id'))
                            if line:
                                line.state = 'failed'
                        msg = f"❌ Failed to update simple products: {response}"
                        rec.state = 'failed'
                        _logger.error(msg)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'inventory', 'export', rec.instance_id, msg, product_updates_simple,
                            json.dumps(response), log_id, True
                        )
                except Exception as e:
                    _logger.error(f"Error updating simple products: {str(e)}")

            # === 🟣 Update VARIANT products ===
            for parent_id, variant_updates in variant_updates_map.items():
                try:
                    api_url = f"{rec.instance_id.woocommerce_url}/wp-json/wc/v3/products/{parent_id}/variations/batch"
                    request_data = json.dumps({"update": variant_updates})
                    success, response, _ = rec.instance_id.woocommerce_api_calling_process(
                        request_type='POST', api_url=api_url, request_data=request_data
                    )

                    if success:
                        for prod in variant_updates:
                            line = line_map.get(prod.get('id'))
                            if line:
                                line.state = 'completed'
                        msg = f"✅ Updated {len(variant_updates)} variants (Parent ID: {parent_id}) successfully."
                        rec.state = 'completed'
                        _logger.info(msg)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'inventory', 'export', rec.instance_id, msg, variant_updates,
                            json.dumps(response), log_id, False
                        )
                    else:
                        for prod in variant_updates:
                            line = line_map.get(prod.get('id'))
                            if line:
                                line.state = 'failed'
                        msg = f"❌ Failed to update variants for product {parent_id}. Response: {response}"
                        rec.state = 'failed'
                        _logger.error(msg)
                        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                            'inventory', 'export', rec.instance_id, msg, variant_updates,
                            json.dumps(response), log_id, True
                        )
                except Exception as e:
                    _logger.error(f"Error updating variants for parent {parent_id}: {str(e)}")

            rec.woocommerce_log_id = log_id
            log_id.woocommerce_operation_message = 'Process Finished'

            if not log_id.woocommerce_operation_line_ids:
                log_id.unlink()

        return True


class WoocommerceInventoryDataQueueLine(models.Model):
    _name = "woocommerce.inventory.data.queue.line"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    product_id = fields.Many2one('product.product')
    woocommerce_inventory_queue_id = fields.Many2one(
        'woocommerce.inventory.data.queue', string='Inventory Data Queue'
    )
    instance_id = fields.Many2one('woocommerce.instance.integration', string='Instance', help='Select Instance Id')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='draft'
    )
    inventory_data_to_process = fields.Text(string="Inventory Data")
    number_of_fails = fields.Integer(
        string="Number of attempts",
        help="Number of times we retried processing this queue line",
        copy=False
    )

    def create_woocommerce_inventory_queue_line(self, product_id, woocommerce_product_id, stock_quantity, instance_id, queue_id, log_id):
        """
        Create or update queue line with product data stored as dict in inventory_data_to_process.
        """
        data_dict = {
            "woocommerce_product_id": woocommerce_product_id,
            "stock_quantity": int(stock_quantity),
        }

        existing_line = self.search([
            ('product_id', '=', product_id),
            ('state', '=', 'draft'),
            ('woocommerce_inventory_queue_id', '=', queue_id.id)
        ], limit=1)

        if existing_line:
            existing_line.inventory_data_to_process = json.dumps(data_dict)
            msg = f"Updated inventory queue line for product {existing_line.product_id.display_name}"
            self.env['woocommerce.log.line'].generate_woocommerce_process_line(
                'inventory', 'export', instance_id, msg, data_dict, msg, log_id, False
            )
            return existing_line

        line = self.create({
            'product_id': product_id,
            'inventory_data_to_process': json.dumps(data_dict),
            'state': 'draft',
            'instance_id': instance_id.id,
            'woocommerce_inventory_queue_id': queue_id.id,
        })
        msg = f"New inventory queue line created for product {line.product_id.display_name}"
        self.env['woocommerce.log.line'].generate_woocommerce_process_line(
            'inventory', 'export', instance_id, msg, data_dict, msg, log_id, False
        )
        return line
