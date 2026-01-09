{
    'name': 'Personnalisation des modules projet et stock',
    'version': '1.0.0',
    'sequence': -10,
    'summary': '''Ce module permet de personnaliser les projects et la gestion des stock, 
                notamment pour la gestion des poulaillers''',
    'description': '''Ce module permet de personnaliser les projects et la gestion des stock, 
                notamment pour la gestion des poulaillers''',
    'category': 'Projects et Stock',
    'author': 'Succès de partenaire',
    'website': 'https://www.partenairesucces.com/',
    'depends': [
        'base',
        'project',
        'stock',
        'sale',
        'purchase'
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/data_product.xml',
        'views/project_project_inherit_views.xml',
        'views/stock_inherit_views.xml',
        'views/product_inherit_views.xml',
        'wizard/product_select_wizard_views.xml',

    ],

    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False
}
