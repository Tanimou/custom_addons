# -*- coding: utf-8 -*-
{
    'name': 'Gestion des Expéditions',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Gestion des colis pour transport aérien et maritime avec suivi',
    'description': """
Gestion des Expéditions - Shipment Tracking
===========================================

Ce module permet de gérer les demandes d'expédition pour le transport aérien et maritime:

* Création automatique de demandes d'expédition depuis les commandes CRM confirmées
* Numérotation des colis avec préfixe AB et sous-références (AB0001-1, AB0001-2, ...)
* Suivi des statuts: Enregistré, Groupage, En transit, Arrivé à destination, Livré
* Génération de liens de tracking publics pour les clients
* Impression d'étiquettes PDF pour les colis
* Vue Kanban pour le suivi opérationnel

Fonctionnalités principales:
----------------------------
* Intégration CRM/Ventes pour création automatique
* Gestion multi-colis par expédition
* Informations transport aérien (vol, aéroports, dates)
* Informations transport maritime (navire, ports, conteneur)
* Page de tracking publique (sans authentification)
* Étiquettes colis avec logo, numéro, client, destination
    """,
    'author': 'Custom Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'crm',
        'sale',
        'website',
    ],
    'data': [
        # Security
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequences.xml',
        # Views
        'views/shipment_request_views.xml',
        'views/shipment_parcel_views.xml',
        'views/tracking_link_views.xml',
        'views/tracking_event_views.xml',
        'views/tracking_page_templates.xml',
        'views/menu_actions.xml',
        # Wizards
        'wizard/parcel_product_wizard_views.xml',
        'wizard/shipment_regrouping_wizard_views.xml',
        # Reports
        'report/parcel_label_templates.xml',
        'report/report_actions.xml',
    ],
    'assets': {},
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
