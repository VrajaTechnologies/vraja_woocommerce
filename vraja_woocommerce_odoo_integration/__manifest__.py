# -*- coding: utf-8 -*-pack
{  # App information
    'name': 'WooCommerce to Odoo Connector',
    'category': '',
    'version': '16.0.0',
    'summary': """""",
    'description': """ """,
    'depends': ['delivery', 'sale_stock', 'sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/woocommerce_operations_view.xml',
        'data/product_data.xml',
        'views/order_data_queue.xml',
        'views/woocommerce_instance_integration.xml',
        'views/woocommerce_log.xml',
        'views/woocommerce_payment_gateway.xml',
        'views/woocommerce_shipping_method.xml',
        'views/woocommerce_product_listing.xml',
        'views/woocommerce_product_listing_item.xml',
        'views/woocommerce_product_image.xml',
        'views/customer_data_queue.xml',
        'views/woocommerce_product_category.xml',
        'views/woocommerce_product_tags.xml',
        'views/woocomerce_financial_status_configuration.xml',  # ⬅ moved BEFORE menu
        'views/woocommerce_order_workflow_automation.xml',
        'views/menu_item.xml',  # ⬅ menus should always come after actions
        'views/res_partner_view.xml',
        'views/sale_order.xml',
        'views/delivery_carrier.xml',
        'views/product_data_queue.xml'

    ],

    'images': [],
    'author': 'Vraja Technologies',
    'maintainer': 'Vraja Technologies',
    'website': 'https://www.vrajatechnologies.com',
    'live_test_url': 'https://www.vrajatechnologies.com/contactus',
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
