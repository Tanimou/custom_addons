# Guide utilisateur – Réseau Partenaires du Parc Automobile

Ce guide explique comment utiliser les fonctionnalités du module 
`custom_fleet_partner_network` (Phases 1 à 3). Il s'adresse aux équipes
opérationnelles, responsables de flotte et gestionnaires qui utilisent Odoo 19.

---

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Navigation principale](#2-navigation-principale)
3. [Phase 1 – Profils Partenaires](#3-phase-1--profils-partenaires)
4. [Phase 2 – Contrats Partenaires](#4-phase-2--contrats-partenaires)
5. [Phase 3 – Gestion des Incidents](#5-phase-3--gestion-des-incidents)
6. [Paramètres et Configuration](#6-paramètres-et-configuration)
7. [Checklist de validation](#7-checklist-de-validation)
8. [Annexes](#8-annexes)

---

## 1. Prérequis

| Élément | Détails |
| --- | --- |
| Modules installés | `fleet`, `mail`, `calendar`, `board`, `custom_fleet_management`, `custom_fleet_maintenance`, `custom_supplier_approval`, `custom_fleet_partner_network` |
| Droits minimum | Groupe `Utilisateur Réseau Partenaires` (`custom_fleet_partner_network.group_fleet_partner_user`) |
| Données nécessaires | Au moins un partenaire approuvé (issue de `custom_supplier_approval`). Pour des tests rapides, créez un partenaire fournisseur standard puis un profil Fleet. |
| Préparation multi-société | Vérifier que la société active est celle sur laquelle vous validez les profils. |

> 💡 **Astuce** : activez le mode développeur pour identifier rapidement les IDs
des vues et vérifier les domaines.

---

## 2. Navigation principale

1. Connectez-vous avec un utilisateur membre du groupe Réseau Partenaires.
2. Ouvrez le module **Parc Automobile** (menu principal Fleet).
3. Dans le sous-menu **Réseau Partenaires**, vous trouverez :
   - **Profils Partenaires** – Liste des assureurs, garages et remorqueurs
   - **Contrats** – Historique des contrats par véhicule
   - **Incidents** – Tickets de pannes, accidents et interventions
   - **Déclarer un incident** – Assistant rapide de création

```
Parc Automobile
└── Réseau Partenaires
    ├── Profils Partenaires
    ├── Contrats
    ├── Incidents
    │   ├── Tous les incidents
    │   └── Déclarer un incident
    └── Configuration
        └── Paramètres
```

---

## 3. Phase 1 – Profils Partenaires

Les **profils partenaires** centralisent les informations sur vos assureurs, 
garages et remorqueurs agréés.

### 3.1 Vue Liste des profils

- **Accès** : Parc Automobile → Réseau Partenaires → Profils Partenaires
- **Colonnes affichées** : Référence, Nom, Type (badge), Partenaire, Zones, SLA
- **Décorations** :
  - 🟢 Vert : profil approuvé par le module fournisseur
  - ⚪ Grisé : profil archivé (inactif)

### 3.2 Créer un profil

1. Cliquez sur **Créer**
2. Renseignez les champs obligatoires :
   - **Type** : Assureur, Garage ou Remorqueur
   - **Partenaire** : sélectionnez ou créez le contact
   - **Contact principal** : personne de référence
3. Ajustez les informations complémentaires :
   - **Zones couvertes** : régions d'intervention
   - **Services proposés** : spécialités (ex: carrosserie, mécanique)
   - **SLA intervention** : délai garanti en heures
4. Enregistrez : une référence unique est générée (ex: `FPP-0001`)

### 3.3 Vue Kanban

- Affiche les profils regroupés par type
- Badges "Approuvé" visibles sur chaque carte
- Cliquez sur la pastille de couleur pour personnaliser

### 3.4 Filtres et recherche

| Filtre | Description |
|--------|-------------|
| Assureurs | Affiche uniquement les assureurs |
| Garages | Affiche uniquement les garages |
| Remorqueurs | Affiche uniquement les remorqueurs |
| Approuvés | Partenaires validés par le système fournisseur |
| Actifs | Exclut les profils archivés |

**Regroupements disponibles** : par Type, par Société

### 3.5 Smart buttons sur res.partner

Depuis la fiche d'un partenaire :
- Bouton **Profils Fleet** : affiche le nombre de profils liés
- Bouton **Créer un profil Fleet** : ouvre le formulaire pré-rempli

---

## 4. Phase 2 – Contrats Partenaires

Les **contrats** tracent l'historique des engagements entre vos véhicules et 
les partenaires (assurances, conventions garage, abonnements remorquage).

### 4.1 Accéder aux contrats

- **Accès** : Parc Automobile → Réseau Partenaires → Contrats
- **Depuis un véhicule** : onglet "Partenaires" → bouton "Contrats"

### 4.2 Créer un contrat

1. Cliquez sur **Créer**
2. Renseignez :
   - **Véhicule** : véhicule concerné
   - **Partenaire** : profil assureur/garage/remorqueur
   - **Dates** : début et fin de validité
   - **Montant** : coût annuel ou périodique
3. Joignez les documents (police d'assurance, devis, etc.)
4. Enregistrez : référence générée (ex: `CNT-0001`)

### 4.3 Workflow des contrats

```
┌─────────┐    ┌────────┐    ┌─────────┐
│Brouillon│ →  │ Actif  │ →  │ Expiré  │
└─────────┘    └────────┘    └─────────┘
                    ↓
              ┌──────────┐
              │ Annulé   │
              └──────────┘
```

| État | Description |
|------|-------------|
| **Brouillon** | Contrat en préparation |
| **Actif** | Contrat en cours de validité |
| **Expiré** | Date de fin dépassée |
| **Annulé** | Résiliation anticipée |

### 4.4 Alertes d'expiration

- Les contrats à moins de 30 jours de l'échéance apparaissent en orange
- Un cron quotidien envoie des rappels aux responsables
- Les contrats expirés sont automatiquement marqués

### 4.5 Vues disponibles

| Vue | Usage |
|-----|-------|
| Liste | Vue principale avec filtres |
| Formulaire | Détail complet avec onglets |
| Kanban | Aperçu par état |
| Calendrier | Visualisation des périodes |
| Pivot | Analyse des coûts par véhicule/partenaire |

---

## 5. Phase 3 – Gestion des Incidents

Le module **Incidents** permet de déclarer et suivre les pannes, accidents et 
interventions véhicule de bout en bout.

### 5.1 Déclarer un incident (Assistant)

**Méthode rapide** :
1. Parc Automobile → Réseau Partenaires → Incidents → **Déclarer un incident**
2. Remplissez l'assistant :
   - Sélectionnez le **véhicule**
   - Choisissez le **type** (Panne, Accident, Vol, Vandalisme)
   - Indiquez le **lieu** et la **date**
   - Décrivez brièvement l'incident
3. Options disponibles :
   - ☑️ **Démarrer le remorquage** : passe directement à l'état "Remorquage"
   - ☑️ **Créer une intervention** : planifie une intervention maintenance
4. Cliquez sur **Créer le ticket**

**Depuis un véhicule** :
- Ouvrez la fiche véhicule → bouton d'action **Déclarer un incident**
- Le véhicule et le conducteur sont pré-remplis

### 5.2 Workflow des incidents

```
┌──────────┐    ┌───────────┐    ┌────────────┐    ┌─────────┐
│ Brouillon│ →  │ Remorquage│ →  │ Réparation │ →  │ Clôturé │
└──────────┘    └───────────┘    └────────────┘    └─────────┘
      ↓              ↓                 ↓
┌──────────┐
│ Annulé   │
└──────────┘
```

| État | Description | Actions |
|------|-------------|---------|
| **Brouillon** | Ticket créé, en attente | Démarrer remorquage |
| **Remorquage** | Véhicule en cours de récupération | Confirmer livraison garage |
| **Réparation** | Véhicule au garage | Clôturer l'incident |
| **Clôturé** | Intervention terminée | Rouvrir si besoin |
| **Annulé** | Ticket invalidé | - |

### 5.3 Informations du ticket

**Onglet Général** :
- Véhicule, conducteur, immatriculation
- Type et priorité (Normale, Haute, Urgente, Critique)
- Lieu et date de l'incident
- Description détaillée

**Onglet Partenaires** :
- Remorqueur assigné (depuis les profils)
- Garage assigné (depuis les profils)
- Dates d'intervention prévues

**Onglet Coûts** :
- Coûts estimés et réels (remorquage, réparation)
- Lien avec l'intervention maintenance

**Onglet Documents** :
- Photos, constats, devis
- Factures et justificatifs

### 5.4 Vues disponibles

| Vue | Usage |
|-----|-------|
| Liste | Vue principale triée par date |
| Formulaire | Détail complet avec workflow |
| Kanban | Suivi visuel par état |
| Calendrier | Planning des incidents |
| Pivot | Analyse par type/véhicule |
| Graphique | Statistiques visuelles |

### 5.5 Filtres incidents

| Filtre | Description |
|--------|-------------|
| Brouillon | Tickets en attente |
| Remorquage | Véhicules en cours de récupération |
| Réparation | Véhicules au garage |
| Clôturé | Incidents terminés |
| Pannes | Incidents de type panne |
| Accidents | Incidents de type accident |
| Priorité haute | Urgences (priorité 2-3) |
| Mes incidents | Tickets dont je suis responsable |

### 5.6 Notifications automatiques

Le module envoie des emails automatiques :
- **Création d'incident** : notification au responsable
- **Affectation remorqueur** : confirmation au partenaire
- **Réparation terminée** : notification de clôture
- **Rappels** : relances pour tickets en attente

---

## 6. Paramètres et Configuration

**Accès** : Paramètres → Paramètres généraux → section Parc Automobile

### 6.1 Garages et remorqueurs par défaut

- **Garage par défaut** : profil garage utilisé par défaut pour les interventions
- **Remorqueur par défaut** : profil remorqueur utilisé par défaut

### 6.2 Alertes et délais

- **Délai alerte contrat** : nombre de jours avant expiration (défaut: 30)
- **Activer notifications** : active/désactive les emails automatiques

> 💡 Ces paramètres sont configurables par société en mode multi-société.

---

## 7. Checklist de validation

### Phase 1 – Profils Partenaires

| # | Fonction | OK / NOK |
|---|----------|----------|
| 1 | Menu Réseau Partenaires visible | [ ] |
| 2 | Vue liste (badges + décorations) | [ ] |
| 3 | Formulaire (onglets, colorpicker, pièces jointes) | [ ] |
| 4 | Kanban (badges "Approuvé") | [ ] |
| 5 | Filtres et regroupements | [ ] |
| 6 | Smart buttons sur res.partner | [ ] |
| 7 | Isolation multi-société | [ ] |

### Phase 2 – Contrats

| # | Fonction | OK / NOK |
|---|----------|----------|
| 8 | Création contrat depuis véhicule | [ ] |
| 9 | Workflow brouillon → actif → expiré | [ ] |
| 10 | Alertes expiration 30 jours | [ ] |
| 11 | Vues calendrier et pivot | [ ] |
| 12 | Documents attachés au contrat | [ ] |

### Phase 3 – Incidents

| # | Fonction | OK / NOK |
|---|----------|----------|
| 13 | Assistant "Déclarer un incident" | [ ] |
| 14 | Workflow brouillon → remorquage → réparation → clôturé | [ ] |
| 15 | Affectation remorqueur et garage | [ ] |
| 16 | Suivi des coûts estimés/réels | [ ] |
| 17 | Vues kanban et calendrier incidents | [ ] |
| 18 | Notifications email automatiques | [ ] |

---

## 8. Annexes

### 8.1 Références des séquences

| Modèle | Préfixe | Exemple |
|--------|---------|---------|
| Profil partenaire | FPP | FPP-0001 |
| Contrat | CNT | CNT-0001 |
| Incident | PNR | PNR-0001 |

### 8.2 Groupes de sécurité

| Groupe | Droits |
|--------|--------|
| Utilisateur Réseau Partenaires | Lecture/création/modification |
| Responsable Réseau Partenaires | Tous droits + suppression |

### 8.3 Raccourcis clavier

- `Alt+Shift+N` : Nouveau profil/contrat/incident (selon vue active)
- `Ctrl+S` : Enregistrer
- `Ctrl+D` : Dupliquer

### 8.4 Support

Pour toute question ou anomalie :
- Consultez la documentation technique dans `/docs/`
- Contactez l'équipe développement Odoo

---

*Document mis à jour le 27 novembre 2025 – Version 3.0 (Phases 1-3)*
