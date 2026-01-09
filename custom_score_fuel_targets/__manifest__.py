# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Fuel Targets',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Fuel consumption targets by family, variance detection, and over-consumption alerts',
    'description': """
SCORE Fuel Consumption Targets
==============================

Gestion des cibles de consommation carburant pour la suite SCORE.

Fonctionnalités:
- Cible de consommation L/100km par famille d'engins (FR-024)
- Comparaison consommation réelle vs cible
- Alertes de surconsommation (FR-025)
- Historique détaillé par véhicule (FR-023)
- Reporting des écarts

FR Coverage: FR-023, FR-024, FR-025
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_fleet_fuel_management',
        'custom_fleet_management',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Data
        # 'data/ir_sequence_data.xml',
        'data/score_fuel_targets.xml',
        # Views
        'views/fleet_vehicle_model_category_views.xml',
        'views/fleet_fuel_monthly_summary_views.xml',
        'views/fleet_fuel_views.xml',
        'views/fleet_vehicle_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
