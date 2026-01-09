# Guide utilisateur — Gestion poulailler (module `custom_kedousha`)

Ce guide explique **comment utiliser** le module `custom_kedousha` dans Odoo (côté utilisateur final), et **comment tester** que tout fonctionne.

> Important : ce module s’appuie sur les applications Odoo **Projet** et **Inventaire / Stock**. Il **personnalise** surtout :
>
> - la gestion d’un **cycle d’élevage** dans un **projet** (poulailler, lot/bande, durée de cycle, mortalité),
> - la création (optionnelle) d’un **projet** à partir d’une **réception** (poussins),
> - la **collecte d’œufs** depuis le projet, avec génération automatique d’une **réception de stock**,
> - le **rebut (mortalité)** avec mise à jour automatique des indicateurs du projet,
> - un assistant pour **ajouter plusieurs produits** rapidement sur un transfert.

---

## 1) Pour qui ?

- **Magasinier / Responsable stock** : réceptionner poussins/œufs, valider les transferts, saisir les rebuts.
- **Responsable élevage** : suivre un cycle d’élevage via un projet (poulailler, lot/bande, mortalité), enregistrer les collectes d’œufs.
- **Administrateur** : paramétrer les produits (poussin/œuf), les poulaillers (emplacements + responsables), vérifier l’accès.

---

## 2) Ce que fait le module (en simple)

- Un **Projet** représente un **cycle d’élevage**.
- Un **Poulailler** est représenté par un **emplacement de stock** (`stock.location`) auquel on affecte des **responsables**.
- Les **poussins** et les **œufs** sont identifiés via des cases à cocher sur les produits :
  - *Est un poussin* (`is_chick`)
  - *Est un oeuf* (`is_egg`)
- Les **réceptions** (stock.picking entrants) permettent :
  - de calculer automatiquement le **nombre de poussins reçus** (somme des lignes “poussin”),
  - de **créer un projet** et d’y associer le poulailler / date / quantité reçue.
- Une **collecte d’œufs** enregistrée dans un projet :
  - crée automatiquement une **réception de stock** pour les produits œufs,
  - et passe en **“Validé”** lorsque la réception est validée.
- Un **rebut** (stock.scrap) lié à un lot/bande et un poulailler met à jour le projet :
  - **nombre de poussins morts**,
  - **poussins vivants** (calcul),
  - **taux de mortalité** (calcul).

---

## 3) Pré-requis avant de tester

1. Les applications doivent être installées : **Projet** et **Inventaire / Stock**.
2. Le module `custom_kedousha` doit être installé.
3. Des produits doivent être correctement configurés :
   - au moins un produit **poussin** (*Est un poussin*),
   - au moins un produit **œuf** (*Est un oeuf*) si vous utilisez la collecte d’œufs.
4. Les **poulaillers** doivent exister dans **Inventaire → Configuration → Emplacements**.
5. Chaque poulailler doit avoir des **responsables** (champ “Responsables”) afin d’être sélectionnable.

> Note : le module charge aussi des produits de base (données) comme des poussins (chair/pondeuse) et un produit “Carton d’oeuf”.

---

## 4) Paramétrage (Administrateur)

### A. Configurer les produits “poussin” et “œuf”

Chemin : **Produits → Produits** (ouvrir un produit)

Dans les options du produit, vous trouverez :

- **Est un poussin**
- **Est un oeuf**

✅ Résultat attendu :

- les réceptions calculent automatiquement le nombre de poussins reçus à partir des lignes dont *Est un poussin* est coché,
- la collecte d’œufs ne permet de sélectionner que des produits dont *Est un oeuf* est coché.

### B. Configurer les poulaillers (emplacements) et responsables

Chemin : **Inventaire → Configuration → Emplacements**

Sur l’emplacement “Poulailler”, renseigner :

- **Responsables** (liste d’utilisateurs)

✅ Résultat attendu :

- dans les projets, le champ **Poulailler** ne propose que les emplacements où l’utilisateur courant est responsable.

### C. (Optionnel) Préparer les lots/bandes

Le module utilise un **Lot/Bande** (`stock.lot`) pour relier :

- un projet (champ **Lot/Bande**),
- un rebut (champ lot renommé “Lot/Bande Associé”).

Recommandation : créez/nommez vos lots/bandes de manière standardisée (ex. `BANDE-2026-01`).

---

## 5) Utilisation côté Stock — Réception de poussins (et création de projet)

### A. Créer une réception

1. Aller dans **Inventaire → Opérations → Réceptions**
2. Créer une réception
3. Choisir :
   - **Type de réception** :
     - *Poussin de chair* (broiler) ou
     - *Poussin pondeur* (laying)
   - **Destination** : le poulailler (emplacement de stock)
4. Ajouter des lignes de produits (des produits *Est un poussin*) et les quantités

✅ Résultat attendu :

- le champ **Nombre de poussins reçus** est calculé automatiquement à partir des lignes “poussin”.

### B. Associer / créer un projet (cycle d’élevage)

Dans la réception, une section **Info Projet** apparaît pour les types de réception “poussins”.

1. Cocher **Générer un nouveau projet**
2. Saisir **Nom du projet**
3. Cliquer sur **Créer un nouveau projet**

✅ Résultat attendu :

- un projet est créé et lié à la réception,
- le projet récupère :
  - le poulailler (destination),
  - la date de réception,
  - le nombre de poussins reçus,
  - et le bon de commande fournisseur si trouvé.

### C. Ouvrir le projet depuis la réception

Dans la réception, cliquer sur le bouton **Projets**.

✅ Résultat attendu : le formulaire du projet associé s’ouvre.

---

## 6) Utilisation côté Projet — Suivi du cycle d’élevage

Chemin : **Projet → Projets**

Dans un projet, vous disposez d’une zone **Info Poulailler** avec :

- **Durée du cycle (en jours)**
- **Lot/Bande**
- **Bons de commande fournisseur**
- **Poulailler**
- **Date de réception des poussins**
- **Nombre de poussins reçus**
- **Nombre de poussins morts**
- **Nombre de poussins vivants** (calcul)
- **Taux de mortalité (%)** (calcul)

✅ Résultat attendu :

- *poussins vivants* = *reçus* − *morts* (jamais négatif),
- le taux de mortalité se met à jour selon les chiffres.

---

## 7) Collecte des œufs (depuis le projet)

Dans le projet, ouvrir l’onglet **Collecte des Oeufs**.

### A. Enregistrer une collecte

1. Ajouter une ligne dans la liste
2. Renseigner :
   - **Produit** (uniquement un produit marqué *Est un oeuf*)
   - **Nombre plaquettes d’oeufs**
   - **Nombre d’oeufs cassé**
   - **Date**
   - (optionnel) **Notes**

✅ Résultat attendu :

- le champ **Total d’oeufs** calcule *plaquettes × 30*,
- une **réception de stock** est automatiquement créée et liée à la collecte (champ **Dossier de livraison** / `picking_id`).

### B. Valider la réception associée

1. Ouvrir le **Dossier de livraison** (réception) lié
2. Valider la réception

✅ Résultat attendu :

- l’état de la collecte passe de **En attente** à **Valider**.

---

## 8) Gestion de la mortalité — Rebut (poussins morts)

Chemin : **Inventaire → Opérations → Rebuts**

1. Créer un rebut
2. Choisir :
   - **Emplacement source** : le poulailler
   - **Lot/Bande Associé** : le lot/bande du cycle
   - **Quantité** : nombre de poussins morts
   - **Projet/Cycle d’élevage** (obligatoire)
3. Valider le rebut

✅ Résultat attendu :

- le projet correspondant (même poulailler + même lot/bande) est mis à jour :
  - **Nombre de poussins morts** augmente,
  - **Nombre de poussins vivants** et **Taux de mortalité** sont recalculés.

---

## 9) Astuce stock — Ajouter plusieurs produits sur un transfert

Dans un transfert (réception, livraison, transfert interne), un bouton est disponible :

- **Ajouter produits (multiple)**

1. Ouvrir un transfert
2. Cliquer sur **Ajouter produits (multiple)**
3. Sélectionner plusieurs produits
4. Cliquer **Ajouter Produits**

✅ Résultat attendu :

- des lignes de mouvement sont ajoutées au transfert (quantité par défaut = 1).

---

## 10) Contrôler l’historique (preuve du test)

Après vos opérations, vérifier :

- Dans le **projet** : indicateurs de cycle, onglet collecte des œufs.
- Dans les **réceptions** :
  - l’association au projet,
  - le type de réception,
  - la réception générée par une collecte.
- Dans les **rebuts** : la présence de l’opération et la mise à jour des champs du projet.

---

## 11) Check-list de test rapide (10–15 minutes)

1. Produit “poussin” : cocher **Est un poussin**
2. Produit “œuf” : cocher **Est un oeuf**
3. Poulailler (emplacement) : définir des **Responsables** incluant votre utilisateur
4. Stock : créer une **réception** de poussins (broiler/laying), ajouter une ligne “poussin”, vérifier **Nombre de poussins reçus**
5. Stock : cocher “Générer un nouveau projet”, saisir le nom, cliquer “Créer un nouveau projet”, ouvrir le projet via “Projets”
6. Projet : vérifier les champs (poulailler, reçus, taux)
7. Projet : créer une **collecte d’œufs**, vérifier la création de la réception liée
8. Stock : valider la réception d’œufs, vérifier que la collecte passe en **Valider**
9. Stock : créer un **rebut** (mortalité) sur le lot/bande + poulailler, vérifier l’augmentation des morts et le recalcul du taux

---

## 12) Emplacements pour captures d’écran

- [CAPTURE] Produit : options “Est un poussin / Est un oeuf”
- [CAPTURE] Emplacement poulailler : champ “Responsables”
- [CAPTURE] Réception : champ “Type de réception” + section “Info Projet”
- [CAPTURE] Réception : bouton “Créer un nouveau projet”
- [CAPTURE] Réception : bouton “Projets”
- [CAPTURE] Projet : zone “Info Poulailler”
- [CAPTURE] Projet : onglet “Collecte des Oeufs”
- [CAPTURE] Collecte : réception générée (picking lié)
- [CAPTURE] Rebut : champs Lot/Bande + Projet/Cycle + validation
