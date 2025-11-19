# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Point of Sale - Bon d'achat",
    'version': '1.0',
    'category': 'Sales/Point Of Sale',
    'sequence': 7,
    'summary': "Single-use POS-only vouchers (Bon d'achat)",
    'description': """
        Point of Sale - Bon d'achat
        ============================
        
        This module extends the loyalty program functionality to add a new program type:
        "Bon d'achat" - Single-use, POS-only vouchers.
        
        Key Features:
        -------------
        * Single-use vouchers: Once used, the code is fully consumed even if the order 
          total is smaller than the voucher amount
        * POS-only: These vouchers can only be used in Point of Sale, not in eCommerce
        * Reuses existing coupon generation and management infrastructure
        * Full French language support
    """,
    'depends': ['loyalty', 'pos_loyalty'],
    'data': [
        'security/ir.model.access.csv',
        'data/pos_payment_method_data.xml',
        'views/loyalty_program_views.xml',
        'views/loyalty_card_views.xml',
        'views/pos_payment_method_views.xml',
        'wizard/loyalty_generate_wizard_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_bon_achat/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
