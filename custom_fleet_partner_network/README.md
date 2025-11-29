# Réseau Partenaires du Parc Automobile

Le module `custom_fleet_partner_network` centralise la gestion des assureurs,
garages et remorqueurs au sein d'Odoo 19. Il s'appuie sur les modules
`custom_fleet_management`, `custom_fleet_maintenance` et
`custom_supplier_approval` pour orchestrer les contrats, incidents et
notifications liées au parc automobile.

## Portée fonctionnelle

- Profils partenaires détaillés avec SLA, zones et documents.
- Liaison des véhicules avec leurs assureurs, garages et remorqueurs agréés.
- Gestion d'incidents (pannes/remorquages) intégrée aux interventions
  de maintenance.
- Alertes automatisées (emails, cron) et reporting analytique.

## Fonctionnalités livrées

### Phase 1 – Profils partenaires

- Modèle `fleet.partner.profile` (mail.thread + activity) avec champs SLA,
  zones d'intervention, services et documents contractuels.
- Sécurité de base : groupes dédiés, ACLs utilisateurs/managers et règle
  multi-société.
- Vues complètes (tree/form/kanban/search) + menu « Réseau Partenaires » sous
  Parc Automobile.
- Intégration `res.partner` : smart buttons, section de synthèse et actions
  pour consulter/créer un profil Fleet.
- Tests unitaires `tests/test_fleet_partner.py` validant le lien partenaire ↔
  profil.

## Scénarios de test rapide

1. Aller dans **Parc Automobile → Réseau Partenaires → Profils Partenaires** et
   créer un profil (type, partenaire, SLA). Vérifier que la règle multi-société
   respecte la société active.
2. Ouvrir la fiche du partenaire utilisé : le smart button « Profils Fleet »
   doit afficher `1`, la section « Références Parc Auto » expose la référence
   et le contact principal.
3. Depuis la fiche partenaire, cliquer sur « Créer un profil Fleet » ouvre un
   formulaire pré-rempli avec le partenaire par défaut.

Ce fichier sera enrichi au fil des autres phases (contrats, incidents,
reporting).

## Documentation utilisateur

- [Guide de tests visuels](docs/USER_GUIDE.md) : parcours détaillés pour
  valider les écrans (listes, formulaires, kanban, filtres, smart buttons et
  multi-société).
