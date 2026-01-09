# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Vehicle',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Vehicle management delta: uniqueness, registration cases, transfers, operational status, reception expenses',
    'description': """
SCORE Vehicle Management
========================

Delta module for vehicle/equipment management in the SCORE Logistics Suite.

Fonctionnalités:
- Unicité conditionnelle (châssis / immatriculation)
- Identifiant interne unique (FR-003)
- Champ provenance (FR-002)
- Dossier d'immatriculation avec workflow (En cours / Validé / Rejeté)
- Statut opérationnel + historique (FR-011)
- Transferts d'engins entre sites/emplacements (FR-016)
- Localisation courante du véhicule
- KPI conducteur/équipe (FR-010)
- Frais de réception véhicule (FR-009)

FR Coverage: FR-002, FR-003, FR-004, FR-008, FR-008a, FR-009, FR-010, FR-011, FR-016
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_fleet_management',
        'stock',
        'account',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/score_vehicle_rules.xml',
        # Data
        'data/ir_sequence_data.xml',
        'data/score_reception_expense_types.xml',
        # Views (actions before menus)
        'views/fleet_vehicle_views.xml',
        'views/fleet_vehicle_registration_case_views.xml',
        'views/fleet_vehicle_transfer_views.xml',
        'views/fleet_vehicle_kpi_reporting_views.xml',
        'views/fleet_vehicle_reception_expense_views.xml',
        'views/score_vehicle_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
