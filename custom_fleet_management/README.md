# Gestion Parc Automobile - Module Odoo 19

## 📋 Vue d'ensemble

**Gestion Parc Automobile** est un module complet pour Odoo 19 Enterprise qui offre une solution intégrée pour gérer l'ensemble du cycle de vie du parc automobile de votre entreprise : véhicules, missions, conformité administrative, alertes automatiques et analyses.

### ✨ Fonctionnalités principales

- **Gestion des véhicules** : Fiches détaillées avec identifiants uniques (VEH-####), historique complet
- **Planification des missions** : Workflow approuvé avec détection automatique des conflits
- **Conformité administrative** : Suivi des échéances, alertes J-30, gestion documentaire
- **Tableau de bord analytique** : KPI temps réel, graphiques, rapports PDF
- **Multi-société** : Support complet avec isolation des données
- **Interface française** : 100% localisée en français

---

## 🎯 Fonctionnalités détaillées

### 🚗 Gestion des Véhicules

- **Identifiant unique automatique** : Code séquentiel VEH-0001, VEH-0002...
- **Informations complètes** : Marque, modèle, catégorie, année, kilométrage, état
- **État administratif** : Calcul automatique basé sur les documents (OK/Avertissement/Critique)
- **Disponibilité** : Vérification en temps réel selon les missions actives
- **Historique** : Missions passées, documents archivés
- **Smart buttons** : Accès rapide aux missions et documents

### 📅 Planification des Missions

- **Workflow complet 7 états** :
  - Brouillon → Soumis → Approuvé → Assigné → En cours → Terminé
  - Possibilité d'annulation avec motif
- **Ordre de mission** : Génération automatique (MIS-####) avec PDF imprimable
- **Détection de conflits** : Véhicule ou conducteur déjà affecté sur période
- **Intégration calendrier** : Synchronisation automatique (optionnelle)
- **Suivi opérationnel** : Kilométrage départ/retour, carburant consommé, itinéraire
- **Vues multiples** : Kanban, liste, calendrier, Gantt, formulaire

### 📄 Conformité Administrative

- **8 types de documents** :
  - Carte grise, Assurance, Visite technique, Vignette
  - Autorisation de circulation, Carte carburant, Permis de conduire, Autre
- **États automatiques** : Valide (vert), À renouveler (orange), Expiré (rouge)
- **Alertes J-30** : Email automatique aux responsables
- **Digest hebdomadaire** : Rapport le lundi matin (configurable)
- **Workflow de renouvellement** : Archivage de l'ancien, création du nouveau
- **Vue timeline** : Visualisation graphique des échéances

### 📊 Tableau de Bord & Reporting

- **4 tuiles KPI** :
  - Véhicules actifs
  - Missions cette semaine
  - Alertes critiques
  - Taux de disponibilité
- **Analyses avancées** :
  - Pivot : Missions par mois/type avec distance et durée
  - Graphique ligne : Tendance sur 6 mois
  - Graphique circulaire : Documents par état
- **Rapports PDF** :
  - **Ordre de mission** : Document imprimable avec QR code, signatures, check-list
  - **Rapport analytique** : Statistiques, top 5 véhicules/conducteurs, recommandations

### 🔒 Sécurité & Permissions

- **3 groupes utilisateurs** :
  - **Fleet User** : Consultation, création missions
  - **Fleet Manager** : Approbation, configuration, rapports
  - **Fleet Driver Portal** : Accès limité à ses propres missions
- **Règles d'enregistrement** :
  - Isolation multi-société stricte
  - Conducteurs voient uniquement leurs missions
  - Documents sensibles protégés
- **Audit trail** : Suivi des modifications (mail.thread)

---

## 📦 Prérequis

### Odoo

- **Version** : Odoo 19.0 Enterprise
- **Base de données** : PostgreSQL 12+

### Modules dépendants

- `base` : Framework Odoo
- `fleet` : Module parc automobile standard
- `hr` : Gestion des employés (conducteurs)
- `mail` : Notifications et suivi
- `calendar` : Intégration événements
- `web` : Interface utilisateur
- `board` : Tableau de bord

---

## 🚀 Installation

### 1. Copier le module

```bash
# Copier le dossier custom_fleet_management dans votre répertoire addons
cp -r custom_fleet_management /path/to/odoo/addons/
```

### 2. Mettre à jour la liste des applications

```bash
# Redémarrer Odoo avec mise à jour de la liste des modules
odoo-bin -c odoo.conf -u all -d votre_base
# OU depuis l'interface Odoo :
# Apps → Update Apps List
```

### 3. Installer le module

1. Connectez-vous en tant qu'administrateur
2. Allez dans **Apps**
3. Retirez le filtre "Apps"
4. Recherchez **"Gestion Parc Automobile"**
5. Cliquez sur **Installer**

### 4. Configuration initiale

Après installation, allez dans **Configuration → Parc Automobile** :

- **Délai d'alerte** : Nombre de jours avant expiration (défaut : 30)
- **Responsables** : Utilisateurs recevant les alertes
- **Alerte hebdomadaire** : Activer/désactiver le digest du lundi
- **Créer événements calendrier** : Synchronisation automatique
- **Bloquer les conflits** : Empêcher les affectations conflictuelles
- **MAJ automatique kilométrage** : Mise à jour du véhicule en fin de mission

---

## 📖 Guide d'utilisation

### Gestion des véhicules

#### Créer un véhicule

1. **Parc Auto → Véhicules → Créer**
2. Remplir les informations (immatriculation, modèle, catégorie)
3. Le code véhicule (VEH-####) est généré automatiquement
4. Ajouter des documents via l'onglet **Administration**

#### Ajouter des documents

1. Ouvrir la fiche véhicule
2. Onglet **Administration** → **Ajouter une ligne**
3. Sélectionner le type, date d'expiration, joindre le fichier scanné
4. L'état et les alertes se calculent automatiquement

### Planification des missions

#### Créer une mission

1. **Parc Auto → Missions → Créer**
2. Remplir : demandeur, conducteur, véhicule, dates, type, itinéraire
3. **Enregistrer** (état = Brouillon)

#### Workflow de validation

1. **Soumettre** : Demande envoyée aux responsables
2. **Approuver** (Manager uniquement) : Validation de la mission
3. **Assigner** : Création de l'événement calendrier (si activé)
4. **Démarrer** : Mission en cours
5. **Terminer** : Saisir kilométrage retour et carburant
6. Le véhicule est mis à jour automatiquement

#### Gestion des conflits

- Affichage automatique si véhicule ou conducteur déjà affecté
- Warning orange (si blocage désactivé) ou erreur bloquante (si activé)
- Détails du conflit affichés dans le champ dédié

### Rapports

#### Ordre de mission (PDF)

1. Ouvrir une mission
2. **Imprimer → Ordre de Mission**
3. Document PDF avec :
   - En-tête avec QR code
   - Détails personnel et véhicule
   - Itinéraire et planning
   - Check-list départ/retour
   - Zones de signatures

#### Rapport analytique (PDF)

1. **Parc Auto → Reporting → Rapport Parc Automobile**
2. Rapport complet avec :
   - KPI (véhicules, missions, alertes)
   - Statistiques par type/mois
   - Top 5 véhicules et conducteurs
   - Véhicules nécessitant attention
   - Recommandations

### Tableau de bord

Accès : **Parc Auto → Tableau de Bord**

- **Colonne gauche** : Graphiques analytiques (véhicules actifs, pivot missions, tendance)
- **Colonne droite** : Opérationnel (missions semaine, alertes critiques, documents)
- Clics sur les tuiles pour filtrer et explorer les données

---

## ⚙️ Configuration avancée

### Personnalisation des types de documents

1. **Configuration → Parc Automobile → Types de Documents**
2. Créer/modifier les types selon vos besoins
3. Cocher **Critique** pour les documents obligatoires

### Ajustement des alertes

```python
# Dans res.config.settings
alert_offset_days = 30  # Modifier selon vos besoins (15, 45, etc.)
```

### Personnalisation des emails

Templates disponibles dans `data/mail_template_fleet.xml` :

- `fleet_document_expiry_alert` : Alerte document expirant
- `fleet_mission_submitted` : Mission soumise
- `fleet_mission_approved` : Mission approuvée
- `fleet_mission_assigned` : Mission assignée
- `fleet_weekly_digest` : Digest hebdomadaire

### Cron jobs

- **Alertes quotidiennes** : Tous les jours à 5h00 (modifiable)
- **Digest hebdomadaire** : Lundis à 7h00 (désactivable)

---

## 🧪 Tests

### Exécuter les tests

```bash
# Tous les tests du module
odoo-bin -c odoo.conf -d test_db -i custom_fleet_management --test-enable --stop-after-init

# Tests spécifiques
odoo-bin -c odoo.conf -d test_db --test-tags custom_fleet_management.test_fleet_vehicle
odoo-bin -c odoo.conf -d test_db --test-tags custom_fleet_management.test_fleet_mission_workflow
odoo-bin -c odoo.conf -d test_db --test-tags custom_fleet_management.test_security
```

### Couverture des tests

- **test_fleet_vehicle.py** : Modèle véhicule, états, disponibilité (12 tests)
- **test_fleet_mission_workflow.py** : Workflow complet, conflits, validation (11 tests)
- **test_security.py** : ACL, règles, multi-société (10 tests)

**Total : 33 tests unitaires**

---

## 🐛 Dépannage

### Les événements calendrier ne se créent pas

- Vérifier : **Configuration → Parc Automobile → Créer événements calendrier** = Activé
- Vérifier que le conducteur a un utilisateur associé

### Les alertes ne sont pas envoyées

- Vérifier que les cron jobs sont actifs : **Paramètres → Technique → Tâches planifiées**
- Vérifier les logs Odoo : `grep "fleet.vehicle.document" odoo.log`
- Vérifier la configuration email du serveur

### Conflit non détecté

- Vérifier : **Configuration → Parc Automobile → Bloquer les conflits** = Activé
- Les missions en état "annulé" ou "terminé" ne génèrent pas de conflits

### Erreur "Accès refusé"

- Vérifier les groupes utilisateurs : **Paramètres → Utilisateurs → Groupes**
- Groupe requis : **Fleet User** minimum, **Fleet Manager** pour approbations

### Module non installable

- Vérifier les dépendances : `fleet`, `hr`, `mail`, `calendar`, `board`
- Consulter les logs : `odoo-bin -c odoo.conf --log-level=debug`

---

## 🔄 Migration / Mise à jour

### Depuis une version antérieure

```bash
# Sauvegarder la base de données
pg_dump -U odoo -Fc votre_base > backup.dump

# Mettre à jour le module
odoo-bin -c odoo.conf -d votre_base -u custom_fleet_management --stop-after-init

# Vérifier les logs
tail -f /var/log/odoo/odoo.log
```

### Données de démonstration

Pour charger des données de test :

```python
# Décommenter dans __manifest__.py :
'demo': [
    'demo/fleet_demo.xml',
],
```

---

## 👥 Contributeurs

**Auteur** : Équipe Développement Odoo  
**Mainteneur** : Votre Entreprise  
**Licence** : LGPL-3  
**Version** : 1.0

---

## 📞 Support

- **Documentation** : Voir ce README
- **Issues** : Ouvrir un ticket sur votre gestionnaire de projet
- **Email** : <support@volistntreprise.com>

---

## 📝 Changelog

### Version 1.0 (2025-11-23)

- ✅ Gestion complète des véhicules avec codes uniques
- ✅ Workflow missions 7 états avec détection conflits
- ✅ Conformité administrative : 8 types documents, alertes J-30
- ✅ Tableau de bord avec KPI et analyses
- ✅ Rapports PDF : ordre de mission + rapport analytique
- ✅ Sécurité : 3 groupes, règles multi-société
- ✅ 33 tests unitaires
- ✅ Documentation complète FR/EN

---

## 🌐 Traductions

- **Français** : 100% (langue par défaut)
- **Anglais** : 100% (voir `i18n/en.po`)

---

## 📄 Licence

Ce module est sous licence **LGPL-3** (GNU Lesser General Public License v3.0).

Vous êtes libre de :

- Utiliser le module à des fins commerciales
- Modifier le code source
- Distribuer le module

Sous conditions de :

- Divulgation du code source modifié
- Même licence pour les dérivés
- Mention des changements

Voir le fichier `LICENSE` pour plus de détails.

---

## 🙏 Remerciements

- Odoo SA pour le framework Odoo
- La communauté OCA pour les bonnes pratiques
- Tous les contributeurs du projet

---

**Développé avec ❤️ pour Odoo 19 Enterprise**
