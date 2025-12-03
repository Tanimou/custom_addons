=================================
Custom Fleet Fuel Management
=================================

.. |badge1| image:: https://img.shields.io/badge/licence-OEEL--1-blue.svg
    :target: https://www.odoo.com/documentation/19.0/legal/licenses.html
    :alt: License: OEEL-1

.. |badge2| image:: https://img.shields.io/badge/version-1.0.0-green.svg
    :alt: Version 1.0.0

.. |badge3| image:: https://img.shields.io/badge/Odoo-19.0-blueviolet.svg
    :alt: Odoo 19.0

|badge1| |badge2| |badge3|

**Table des matières**

.. contents::
   :local:

Description
-----------

Ce module étend la gestion de flotte Odoo avec une solution complète de gestion
des cartes carburant, suivi des dépenses, contrôle budgétaire et indicateurs
de performance (KPI).

Fonctionnalités principales
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Gestion des cartes carburant**

* Cycle de vie complet (brouillon → active → suspendue → expirée)
* Suivi du solde disponible en temps réel
* Montants en attente pour les recharges en cours
* Plafonds quotidiens et mensuels
* Alertes automatiques avant expiration

**Workflow de recharge virtuelle**

* Processus d'approbation multi-étapes (soumission → approbation → comptabilisation)
* Réservation automatique des montants en attente
* Traçabilité complète des validateurs

**Suivi des dépenses**

* Enregistrement manuel avec justificatif obligatoire
* Import en masse via fichier XLSX
* Déduplication automatique par hash (carte + date + montant + litres)
* Workflow de validation (brouillon → soumise → validée/rejetée)
* Calcul automatique du prix au litre

**Synthèses mensuelles et KPI**

* Génération automatique ou manuelle par période
* Calcul de la consommation L/100km
* Suivi de l'écart budgétaire avec alertes
* Agrégation par véhicule, carte ou conducteur

**Tableaux de bord et analytique**

* Dashboard avec cartes KPI
* Vues graphiques (barres, secteurs, lignes)
* Tableaux croisés dynamiques (pivot)
* Filtres avancés par période, véhicule, carte

**Rapports PDF**

* Relevé de carte carburant
* Synthèse mensuelle de consommation

Installation
------------

Dépendances
~~~~~~~~~~~

Ce module requiert les modules suivants :

+---------------------------+------------------------------------------+
| Module                    | Description                              |
+===========================+==========================================+
| ``fleet``                 | Gestion de base de la flotte             |
+---------------------------+------------------------------------------+
| ``hr``                    | Ressources humaines (conducteurs)        |
+---------------------------+------------------------------------------+
| ``account``               | Comptabilité                             |
+---------------------------+------------------------------------------+
| ``account_budget``        | Gestion budgétaire                       |
+---------------------------+------------------------------------------+
| ``analytic``              | Comptabilité analytique                  |
+---------------------------+------------------------------------------+
| ``mail``                  | Messagerie et chatter                    |
+---------------------------+------------------------------------------+
| ``board``                 | Tableaux de bord                         |
+---------------------------+------------------------------------------+
| ``custom_fleet_management``| Gestion de flotte personnalisée (base)  |
+---------------------------+------------------------------------------+
| ``custom_fleet_maintenance``| Maintenance flotte personnalisée       |
+---------------------------+------------------------------------------+

Procédure d'installation
~~~~~~~~~~~~~~~~~~~~~~~~

1. Copier le module dans le répertoire ``addons`` de votre instance Odoo
2. Redémarrer le serveur Odoo
3. Activer le mode développeur
4. Aller dans **Applications** et cliquer sur **Mettre à jour la liste des applications**
5. Rechercher "Custom Fleet Fuel Management"
6. Cliquer sur **Installer**

Configuration
-------------

Paramètres généraux
~~~~~~~~~~~~~~~~~~~

1. Aller dans **Flotte > Configuration > Paramètres**
2. Section **Gestion Carburant** :

   * **Seuil d'alerte (%)** : Pourcentage d'écart budgétaire déclenchant une alerte
     (défaut: 10%). Une alerte "Attention" apparaît entre seuil et 2× seuil,
     "Critique" au-delà de 2× seuil.

   * **Offset alertes (jours)** : Nombre de jours avant expiration de carte
     pour déclencher une notification (défaut: 5 jours).

   * **Journal budget carburant** : Journal comptable par défaut pour les
     écritures liées au budget carburant.

   * **Responsables alertes** : Utilisateurs recevant les notifications
     d'alerte carburant par email.

Automatisation
~~~~~~~~~~~~~~

* **Génération automatique des synthèses** : Active la création automatique
  des synthèses mensuelles via tâche planifiée.

* **Jour de génération mensuelle** : Jour du mois où les synthèses sont
  générées automatiquement (1-28, défaut: 1).

Options de saisie
~~~~~~~~~~~~~~~~~

* **Justificatif obligatoire** : Rend le justificatif obligatoire pour
  valider les dépenses.

* **Suivi odomètre** : Active le champ odomètre sur les dépenses pour le
  calcul de consommation L/100km.

Groupes de sécurité
~~~~~~~~~~~~~~~~~~~

Le module définit trois niveaux d'accès :

* **Utilisateur carburant** : Consultation des cartes et dépenses
* **Gestionnaire carburant** : Création et validation des recharges/dépenses
* **Administrateur carburant** : Configuration complète et accès aux synthèses

Usage
-----

Créer une carte carburant
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Aller dans **Carburant > Cartes carburant**
2. Cliquer sur **Créer**
3. Renseigner :

   * Numéro de carte (unique)
   * Véhicule associé
   * Type de carburant
   * Date d'activation et d'expiration (optionnel)
   * Plafonds quotidien et mensuel (optionnel)

4. Cliquer sur **Enregistrer**
5. Utiliser le bouton **Activer** pour passer la carte en statut actif

Effectuer une recharge
~~~~~~~~~~~~~~~~~~~~~~

1. Depuis une carte carburant, cliquer sur le bouton **Recharges**
   ou aller dans **Carburant > Recharges**
2. Cliquer sur **Créer**
3. Sélectionner la carte et saisir le montant
4. **Soumettre** la recharge (le montant passe en attente sur la carte)
5. Un gestionnaire **Approuve** la recharge
6. Comptabiliser la recharge avec **Poster** (le solde de la carte augmente)

Enregistrer une dépense
~~~~~~~~~~~~~~~~~~~~~~~

1. Aller dans **Carburant > Dépenses**
2. Cliquer sur **Créer**
3. Renseigner :

   * Carte carburant (auto-remplit véhicule/conducteur)
   * Date de la dépense
   * Montant total
   * Quantité en litres
   * Odomètre (si suivi activé)
   * Justificatif (obligatoire)
   * Station service (optionnel)

4. **Soumettre** la dépense
5. Un gestionnaire **Valide** (le solde de la carte diminue)
   ou **Rejette** avec un motif

Importer des dépenses en masse
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Voir la documentation détaillée : `docs/import_fuel_expense.md`

1. Aller dans **Carburant > Dépenses > Lots d'import**
2. Créer un nouveau lot
3. Charger le fichier XLSX au format requis
4. Lancer l'import
5. Consulter le résultat dans l'onglet **Lignes**

Consulter les synthèses mensuelles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Aller dans **Carburant > Rapports > Synthèses mensuelles**
2. Les synthèses sont générées automatiquement (si configuré) ou manuellement
3. Chaque synthèse affiche :

   * Totaux : montant, litres, nombre de dépenses/recharges
   * KPI : consommation L/100km, prix moyen/litre
   * Budget : montant prévu, écart, pourcentage
   * Niveau d'alerte : OK / Attention / Critique

4. Utiliser **Remplir odomètres** pour calculer automatiquement les relevés
   depuis les dépenses
5. **Confirmer** puis **Clôturer** la synthèse après vérification

Utiliser le tableau de bord
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Aller dans **Carburant > Tableau de bord**
2. Visualiser les indicateurs clés :

   * Cartes actives / en alerte
   * Dépenses du mois en cours
   * Graphiques de tendance

3. Utiliser les vues analytiques (pivot, graphique) pour des analyses détaillées

Générer des rapports PDF
~~~~~~~~~~~~~~~~~~~~~~~~

**Relevé de carte :**

1. Ouvrir la fiche d'une carte carburant
2. Cliquer sur **Imprimer > Relevé de carte**
3. Le PDF contient : informations carte, historique recharges, historique dépenses

**Synthèse mensuelle :**

1. Ouvrir une synthèse mensuelle
2. Cliquer sur **Imprimer > Rapport synthèse**
3. Le PDF contient : période, totaux, KPI, graphiques de consommation

Structure technique
-------------------

Modèles
~~~~~~~

+----------------------------------+------------------------------------------+
| Modèle                           | Description                              |
+==================================+==========================================+
| ``fleet.fuel.card``              | Carte carburant avec gestion du solde    |
+----------------------------------+------------------------------------------+
| ``fleet.fuel.recharge``          | Workflow de recharge                     |
+----------------------------------+------------------------------------------+
| ``fleet.fuel.expense``           | Dépense carburant avec validation        |
+----------------------------------+------------------------------------------+
| ``fleet.fuel.expense.batch``     | Lot d'import de dépenses                 |
+----------------------------------+------------------------------------------+
| ``fleet.fuel.expense.batch.line``| Ligne de détail d'import                 |
+----------------------------------+------------------------------------------+
| ``fleet.fuel.monthly.summary``   | Synthèse mensuelle avec KPI              |
+----------------------------------+------------------------------------------+

Services métier
~~~~~~~~~~~~~~~

+------------------------------+----------------------------------------------+
| Service                      | Description                                  |
+==============================+==============================================+
| ``fleet.fuel.balance.service``| Calculs de solde (réservation, débit, crédit)|
+------------------------------+----------------------------------------------+
| ``fleet.fuel.kpi.service``   | Calcul des KPI et génération des synthèses   |
+------------------------------+----------------------------------------------+

Tâches planifiées (Cron)
~~~~~~~~~~~~~~~~~~~~~~~~

* **Génération synthèses mensuelles** : Exécutée quotidiennement, génère les
  synthèses du mois précédent le jour configuré.

* **Envoi alertes carburant** : Vérifie les cartes proches de l'expiration et
  les synthèses en alerte, envoie des notifications.

Règles de sécurité
~~~~~~~~~~~~~~~~~~

* Multi-société : Les utilisateurs ne voient que les données de leur société.
* Record rules : Règles d'accès par groupe (utilisateur/gestionnaire/admin).
* Données sensibles : Soldes et budgets visibles uniquement aux gestionnaires.

Changelog
---------

**Version 1.0.0** (2024-12)

* Version initiale
* Gestion complète des cartes carburant
* Workflow de recharge avec approbation
* Suivi des dépenses avec validation
* Import XLSX des dépenses
* Synthèses mensuelles avec KPI
* Tableau de bord analytique
* Rapports PDF (relevé carte, synthèse mensuelle)
* Alertes automatiques par email

Bugs connus et limitations
--------------------------

* L'import XLSX ne supporte pas les formats XLS (Excel 97-2003)
* Le calcul L/100km nécessite la saisie manuelle de l'odomètre sur chaque dépense
* La déduplication à l'import se base sur un hash exact (carte + date + montant + litres)

Feuille de route
----------------

* Intégration avec les terminaux de paiement (API stations)
* Application mobile pour saisie des dépenses
* OCR pour extraction automatique des tickets
* Intégration avec le module comptable (écritures automatiques)

Crédits
-------

Auteurs
~~~~~~~

* Custom Fleet Team

Contributeurs
~~~~~~~~~~~~~

* Custom Fleet Team

Mainteneurs
~~~~~~~~~~~

Ce module est maintenu par Custom Fleet Team.

Support
~~~~~~~

Pour toute question ou problème, veuillez ouvrir un ticket sur le dépôt
du projet ou contacter l'équipe de support.
