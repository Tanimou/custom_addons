# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Gestion Parc Automobile',
    'version': '1.0',
    'category': 'Operations/Fleet',
    'sequence': 95,
    'summary': 'Gestion intégrée du parc automobile: véhicules, missions, échéances, alertes et tableau de bord',
    'description': """
Gestion Complète du Parc Automobile
====================================

Ce module personnalisé pour Odoo 19 Enterprise offre une solution complète pour gérer le parc automobile de l'entreprise:

**Fonctionnalités principales:**

* **Gestion des véhicules:**
    - Identifiants uniques automatiques (VEH-0001)
    - Fiches détaillées (marque, modèle, catégorie, kilométrage, état)
    - Historisation des affectations conducteurs
    - Gestion multi-sociétés

* **Planification des missions:**
    - Workflow complet (Brouillon → Soumis → Approuvé → En cours → Terminé)
    - Détection automatique des conflits d'affectation
    - Génération d'ordres de mission imprimables avec QR code
    - Synchronisation avec calendrier Odoo (optionnel)

* **Conformité administrative:**
    - Suivi des échéances (visite technique, assurance, documents)
    - Alertes automatiques J-30 avec rappels hebdomadaires
    - Gestion des documents scannés
    - Niveaux d'alerte visuels (vert/orange/rouge)

* **Tableau de bord opérationnel:**
    - KPI en temps réel (véhicules actifs, missions planifiées, alertes)
    - Vues pivot et graphiques analytiques
    - Rapports PDF personnalisés
    - Interface 100% francophone

**Sécurité:**
    - Groupes Fleet User / Fleet Manager / Fleet Dashboard
    - Règles d'accès par conducteur et société
    - Contrôle strict des approbations

""",
    'author': 'Équipe Développement Odoo',
    'website': 'https://www.odoo.com',
    'depends': [
        'base',
        'fleet',
        'hr',
        'mail',
        'calendar',
        'web',
        'board',
    ],
    'data': [
        # Sécurité - doit être chargé en premier
        'security/fleet_groups.xml',
        'security/fleet_security.xml',
        'security/ir.model.access.csv',
        
        # Données de base
        'data/fleet_sequences.xml',
        'data/fleet_document_types.xml',
        'data/mail_template_fleet.xml',
        'data/fleet_cron.xml',
        
        # Wizards (must be loaded before views that reference them)
        'wizards/mission_cancellation_wizard_views.xml',
        
        # Vues
        'views/fleet_vehicle_views.xml',
        'views/fleet_mission_views.xml',
        'views/fleet_document_views.xml',
        'views/res_config_settings_views.xml',
        'views/fleet_menu.xml',
        'views/fleet_dashboard.xml',
        
        # Rapports
        'report/mission_order_report.xml',
        'report/fleet_kpi_report.xml',
    ],
    'demo': [
        # 'demo/fleet_demo.xml',
    ],
    'assets': {
        # Assets JS/CSS si nécessaire pour le dashboard
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
