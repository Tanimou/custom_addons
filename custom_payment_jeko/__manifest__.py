# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: Jeko',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Payment Provider: Jeko - Support pour Wave, Orange Money, MTN, Moov, Djamo',
    'description': """
Payment Provider: Jeko
========================
Intégration avec l'API Jeko Partner pour accepter les paiements via:
- Wave
- Orange Money
- MTN Mobile Money
- Moov Money
- Djamo

Type de paiement supporté:
- Redirect: Redirection vers l'app de paiement mobile pour effectuer le paiement

Fonctionnalités:
- Gestion complète des webhooks avec vérification HMAC-SHA256
- Support multi-magasins
- Devises supportées: XOF, XAF
- Réconciliation automatique des transactions
- Logs détaillés des transactions
    """,
    'author': 'Partenaire Succes',
    'website': 'https://jeko.africa',
    "depends": ["payment", "point_of_sale", "account"],
    "data": [
        # 'security/ir.model.access.csv',
        "views/payment_jeko_templates.xml",
        "views/payment_provider_views.xml",
        "views/payment_method_views.xml",
        "views/pos_payment_method_views.xml",
        "data/payment_method_data.xml",
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'custom_payment_jeko/static/src/**/*',
        ],
    },

    'application': False,
    'installable': True,
    'license': 'LGPL-3',
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
