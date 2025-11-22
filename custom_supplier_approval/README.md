# Supplier Approval & Evaluation Module

## Description

Module personnalisé Odoo 19 pour la gestion complète du cycle de vie des fournisseurs : enregistrement, agrément, évaluation et intégration avec les achats.

## Fonctionnalités

### ✅ Phase 1: Module Structure & Base Models (COMPLETED)

- ✅ Structure de répertoires complète
- ✅ Modèle `supplier.category` - Catégorisation des fournisseurs
- ✅ Modèle `supplier.legal.document` - Gestion des documents légaux (RCCM, NCC, CNPS)
- ✅ Extension `res.partner` avec champs d'agrément et évaluation

### 🚧 Phase 2: Approval Request Workflow (TODO)

- Workflow complet de demande d'agrément
- États: Draft → Pending → Approved/Rejected
- Notifications et activités

### 🚧 Phase 3: Supplier Evaluation System (TODO)

- Système d'évaluation sur 5 critères
- Calcul automatique du taux de satisfaction
- Historique des évaluations

### 🚧 Phase 4: Purchase Module Integration (TODO)

- Restriction des achats aux fournisseurs agréés
- Warnings et contraintes

### 🚧 Phases 5-12: (TODO)

- Vues et interface utilisateur
- Menus et navigation
- Sécurité (ACL/Record Rules)
- Wizards
- Rapports et notifications
- Actions automatisées
- Dashboard analytique
- Tests et documentation

## Installation

1. Copier le module dans `server/addons/custom_supplier_approval/`
2. Redémarrer le serveur Odoo
3. Activer le mode développeur
4. Aller dans Apps > Mettre à jour la liste des applications
5. Rechercher "Supplier Approval"
6. Cliquer sur Installer

## Dépendances

- `base` (Odoo Core)
- `purchase` (Module Achats)
- `mail` (Système de messagerie)

## Configuration

Après installation:

1. Aller dans Achats > Configuration > Catégories fournisseurs
2. Vérifier les catégories par défaut
3. Configurer les droits d'accès pour les utilisateurs

## Structure

```
custom_supplier_approval/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── supplier_category.py
│   ├── supplier_legal_document.py
│   ├── res_partner.py
│   ├── supplier_approval_request.py
│   ├── supplier_evaluation.py
│   └── purchase_order.py
├── views/
│   └── (À venir dans Phase 5)
├── security/
│   ├── ir.model.access.csv
│   └── (À compléter dans Phase 7)
├── data/
│   ├── supplier_category_data.xml
│   └── supplier_approval_sequence.xml
├── wizards/
│   └── (À venir dans Phase 8)
└── report/
    └── (À venir dans Phase 9)
```

## Versions

- Version: 1.0
- Odoo Version: 19.0
- License: LGPL-3

## Auteur

Développement Odoo - Novembre 2025

## Support

Pour toute question ou problème, consulter le plan d'implémentation dans `/plan/feature-supplier-approval-evaluation-1.md`
