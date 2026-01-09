# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Reporting',
    'version': '19.0.1.1.0',
    'category': 'Fleet',
    'summary': 'Dashboards, pivot views, and consolidated KPI reporting for SCORE suite',
    'description': """
SCORE Reporting & Dashboards
============================

Tableaux de bord et rapports consolidés pour la suite SCORE.

Fonctionnalités:
- Tableau de bord principal avec KPIs direction (FR-027)
- Rapports pivot multi-critères (FR-028)
- Export Excel des rapports (FR-029)
- Vue consolidée flotte avec indicateurs (FR-030)
- Rapports par projet/département (FR-017/FR-026)

FR Coverage: FR-017, FR-026, FR-027, FR-028, FR-029, FR-030
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_score_vehicle',
        'custom_score_compliance',
        'custom_score_mission_cost',
        'custom_score_maintenance',
        'custom_score_fuel_targets',
        # Base Odoo
        'board',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Views - Order matters: dashboards first, then detailed reports
        'views/score_dashboards_views.xml',
        'views/score_pivot_reports_views.xml',
        'views/score_kanban_views.xml',
        'views/score_project_views.xml',
        'views/score_analytic_reporting_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
