# -*- coding: utf-8 -*-
# Part of SCORE Logistics Suite. See LICENSE file for full copyright and licensing details.

{
    'name': 'SCORE - Logistics Suite (Bundle)',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Meta-module to install the complete SCORE Logistics Suite',
    'description': """
SCORE Logistics Suite - Complete Bundle
=======================================

Module méta pour installer la suite SCORE complète en une seule opération.

Ce module installe automatiquement tous les modules SCORE:
- SCORE Base (menus racines et transversaux)
- SCORE Vehicle (unicité, matricules, transferts)
- SCORE Compliance (documents, blocage, alertes)
- SCORE Mission Cost (frais, coût/km)
- SCORE Maintenance (KPIs disponibilité)
- SCORE Fuel Targets (cibles consommation)
- SCORE Reporting (tableaux de bord)
- SCORE API (endpoints optionnels)

Usage:
------
Installer ce module unique pour déployer toute la suite SCORE.
    """,
    'author': 'SCORE',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        # All SCORE modules
        'custom_score_base',
        'custom_score_vehicle',
        'custom_score_compliance',
        'custom_score_mission_cost',
        'custom_score_maintenance',
        'custom_score_fuel_targets',
        'custom_score_reporting',
        # Optional but included in bundle
        'custom_score_api',
    ],
    'data': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
