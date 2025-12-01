# -*- coding: utf-8 -*-
# flake8: noqa
# pyright: reportUnusedExpression=false
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# pylint: disable=pointless-statement

{
    'name': 'Réseau Partenaires Parc Auto',
    'version': '1.0.0',
    'category': 'Operations/Fleet',
    'sequence': 120,
    'summary': 'Centralisation des assureurs, garages et remorqueurs pour le parc automobile.',
    'description': """
Gestion collaborative des partenaires stratégiques du parc automobile (assureurs,
garages, remorqueurs) avec intégration aux modules Fleet, Maintenance et
Supplier Approval.
""",
    'author': 'Équipe Développement Odoo',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'fleet',
        'mail',
        'calendar',
        'base_automation',
        'board',
        'custom_fleet_management',
        'custom_fleet_maintenance',
        'custom_supplier_approval',
    ],
    'data': [
        # Sécurité
        'security/fleet_partner_groups.xml',
        'security/fleet_partner_security.xml',
        'security/ir.model.access.csv',

        # Données de base
        'data/fleet_partner_sequences.xml',
        'data/mail_template_partner.xml',
        'data/fleet_partner_cron.xml',
        'data/fleet_partner_automated_actions.xml',

        # Vues et actions
        'views/fleet_partner_profile_views.xml',
        'views/res_partner_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_incident_views.xml',
        'views/fleet_maintenance_intervention_views.xml',
        'views/res_config_settings_views.xml',
        'views/fleet_partner_dashboard.xml',

        # Wizard views (avant menus car actions référencées)
        'views/fleet_incident_wizard_views.xml',

        # Menus (en dernier car référencent les actions)
        'views/fleet_menu.xml',

        # Rapports
        'report/fleet_partner_report.xml',
    ],
    'demo': [],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
}
