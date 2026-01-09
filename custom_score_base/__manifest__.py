# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Base',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Base module for SCORE Logistics Suite - Root menus and cross-cutting elements',
    'description': """
SCORE Base Logistique - Module Socle
====================================

Ce module constitue le socle de la suite SCORE pour la gestion du parc logistique.

Fonctionnalités:
- Menu racine SCORE
- Éléments transverses légers
- Point d'entrée pour les autres modules SCORE

Ce module doit être installé avant tout autre module custom_score_*.
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'custom_fleet_management',
    ],
    'data': [
        # Security
        # 'security/ir.model.access.csv',
        # Data
        # Views
        'views/score_base_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
