{
    'name': 'Reservation de Salle de reunion',
    'summary': '''
        Ce module permet de personnaliser et d'ajouter un flux a la reservation 
        des salles de reunion''',
    'description': '''
        Ce module permet de personnaliser et d'ajouter un flux a la reservation 
        des salles de reunion''',
    'sequence': -20,
    'category': 'room',
    'author': 'Partenaire de succès',
    'website': 'https://www.partenairesucces.com/',
    'depends': [
        'base',
        'product',
        'room',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/reservations_room_views.xml',
        'views/room_room_views.xml',
        'views/config_room_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False
}
