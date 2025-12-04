# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Inventaire des Immobilisations",
    'version': '19.0.2.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Gestion de l'inventaire physique des immobilisations",
    'description': """
Inventaire des Immobilisations
==============================

Ce module permet de gérer l'inventaire physique des immobilisations 
de l'entreprise avec les fonctionnalités suivantes:

**Campagnes d'inventaire**
    - Création de campagnes avec dates de début et fin
    - Périodicité configurable (mensuelle, trimestrielle, annuelle)
    - Affectation par entrepôt et emplacements
    - Suivi du statut (brouillon, en cours, terminé, annulé)

**Lignes d'inventaire**
    - Sélection des PRODUITS à inventorier
    - Liaison automatique avec les immobilisations (account.asset) via le produit
    - Statut physique: présent, manquant, dégradé, à réparer
    - Localisation précise (emplacement stock)
    - Responsable assigné
    - Photos et commentaires

**Valorisation automatique**
    - Valeur nette comptable (VNC) depuis l'immobilisation liée
    - Amortissements cumulés
    - Valeur résiduelle
    - Valorisation d'inventaire

**Assistant de génération**
    - Mode 1: Génération depuis les produits avec immobilisation liée
    - Mode 2: Génération depuis les immobilisations directement
    - Filtrage par catégorie produit, groupe d'actifs, état, entrepôt

**Rapports (Fiche de Contrôle)**
    - Fiche de contrôle individuelle par ligne (PDF)
    - Fiches de contrôle pour toute une campagne
    - Synthèse de campagne avec statistiques

**Extension des produits**
    - Champ 'Immobilisation liée' sur les fiches produits
    - Filtre pour voir les produits avec/sans immobilisation
    """,
    'author': 'Custom Development',
    'website': 'https://www.example.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'stock',
        'account',
        'account_asset',
        'product',
    ],
    # Data files loading order: security first, then data, then reports, then views, then menus
    'data': [
        # Security files first
        'security/custom_asset_inventory_security.xml',
        'security/ir.model.access.csv',
        # Data files (sequences, etc.)
        'data/ir_sequence_data.xml',
        # Report actions and templates (before views that may reference them)
        'report/asset_inventory_report.xml',
        'report/asset_inventory_report_templates.xml',
        'report/report_actions.xml',
        'report/report_fiche_controle_templates.xml',
        # Views before menus (actions must be defined before menus reference them)
        'views/asset_inventory_views.xml',
        # Product views extension (extend product forms to add asset link)
        'views/product_views.xml',
        # Dashboard views (after main views, before menus)
        'views/asset_inventory_dashboard_views.xml',
        # Menus last (they reference actions defined in views)
        'views/custom_asset_inventory_menu.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
