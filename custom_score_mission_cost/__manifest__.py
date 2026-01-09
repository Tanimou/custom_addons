# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Mission Cost',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Mission expenses, cost consolidation, cost/km KPI, and analytic reporting',
    'description': """
SCORE Mission Cost Management
=============================

Gestion des coûts de mission pour la suite SCORE.

Fonctionnalités:
- Dépenses par mission (péage, carburant, entretien, autres)
- Consolidation des coûts mission/projet (FR-014)
- Calcul du coût au kilomètre (FR-015)
- Traçabilité de l'approbation (FR-013b/FR-013c)
- Reporting analytique (FR-026)
- Delta workflow mission si nécessaire (FR-013a)

FR Coverage: FR-013, FR-013a, FR-013b, FR-013c, FR-014, FR-015, FR-026
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_fleet_management',
        'analytic',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/score_mission_cost_rules.xml',
        # Data
        'data/ir_sequence_data.xml',
        # Views
        'views/fleet_mission_expense_views.xml',
        'views/fleet_mission_views.xml',
        'views/fleet_mission_reporting_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
