# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Compliance',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Document compliance: critical types, mission blocking, alerts and reminders',
    'description': """
SCORE Document Compliance
=========================

Conformité documentaire pour la suite SCORE.

Fonctionnalités:
- Types de documents avec flag "critique" (is_critical)
- Blocage mission si document critique expiré (FR-007a)
- Alertes J-30 avant échéance (FR-007)
- Rappels hebdomadaires
- Configuration des points de blocage (soumission, démarrage)
- Migration Selection → Many2one pour document_type

FR Coverage: FR-007, FR-007a
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_fleet_management',
        'mail',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/score_compliance_rules.xml',
        # Data
        'data/score_document_types.xml',
        'data/ir_cron_data.xml',
        # Views
        'views/res_config_settings_views.xml',
        'views/fleet_vehicle_document_type_views.xml',
        'views/fleet_mission_compliance_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': '_post_init_hook_backfill_document_types',
}
