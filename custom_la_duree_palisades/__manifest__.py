{
    'name': 'Personnalisation Stock',
    'version': '1.1.0',
    'summary': 'Ce module permet de personnaliser les inventaires et le POS',
    'description': 'ce module permet de personnaliser les inventaires et le POS',
    'sequence': 50,
    'category': 'Stock',
    'author': 'Partenaire de succès',
    'website': 'https://www.partenairesucces.com/',
    'depends': [
        'base',
        'sale',
        'stock',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/stock_picking_inherit_views.xml',
        'views/employee_credit_limit_view.xml',
        'views/pos_payment_method_inherit_views.xml',
        'views/stock_scrap_loss_view.xml',
        'wizard/product_select_wizard_views.xml',
        'wizard/stock_scrap_loss_report_wizard_view.xml',
        'reports/stock_scrap_loss_report_template.xml',
        ],
    'assets': {
        'pos_self_order.assets': [
            'custom_la_duree_palisades/static/src/js/preset_info_popup_patch.js',
            'custom_la_duree_palisades/static/src/xml/preset_info_popup_inherit.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False
}
