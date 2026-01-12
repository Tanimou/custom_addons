# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Maintenance',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Maintenance delta: downtime KPIs, technician productivity, parts/stock hooks',
    'description': """
SCORE Maintenance Delta
=======================

Extensions de maintenance pour la suite SCORE.

Fonctionnalités:
- Calcul des temps d'arrêt (FR-019)
- Productivité technicien (FR-022)
- Typologie maintenance (curative/préventive) (FR-021)
- Hooks pièces/stock/procurement (FR-020)
- Reporting temps d'arrêt

FR Coverage: FR-019, FR-020, FR-021, FR-022
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_fleet_maintenance',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Views - load technician time first (O2M target)
        'views/fleet_maintenance_technician_time_views.xml',
        'views/fleet_maintenance_intervention_views.xml',
        'views/fleet_maintenance_reporting_views.xml',
        'views/fleet_maintenance_productivity_reporting_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
