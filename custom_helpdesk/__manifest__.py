{
    'name': 'helpdesk ticket',
    'summary': '''
        Ce module permet de personnaliser le module helpdesk''',
    'description': '''
        Ce module permet de personnaliser le module helpdesk''',
    'sequence': -21,
    'category': 'helpdesk',
    'author': 'Partenaire de succès',
    'website': 'https://www.partenairesucces.com/',
    'depends': [
        'base',
        'product',
        'helpdesk',
        'purchase',
        'custom_room',
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'views/helpdesk_ticket_views.xml',
        'views/purchase_order_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False
}
