# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - API',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Optional REST/JSON-RPC API endpoints for external integrations',
    'description': """
SCORE API Endpoints
===================

Points d'accès API optionnels pour intégrations externes.

Fonctionnalités:
- Endpoints REST pour données véhicules
- Endpoints pour missions et coûts
- Endpoints pour documents et conformité
- Authentification token-based (via Odoo auth)

Note: Module optionnel, non requis pour fonctionnement de base.
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_score_base',
        'custom_score_vehicle',
        'custom_score_compliance',
        'custom_score_mission_cost',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
