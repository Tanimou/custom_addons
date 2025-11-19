# Installation et Test du Module pos_bon_achat

## Installation

### Étape 1: Vérifier les prérequis

Le module nécessite:

- Odoo 19.0
- Module `loyalty` installé
- Module `pos_loyalty` installé
- Module `point_of_sale` installé

### Étape 2: Installer le module

1. Aller dans **Paramètres → Apps → Mettre à jour la liste des Apps**
2. Rechercher "pos_bon_achat" ou "Bon d'achat"
3. Cliquer sur **Installer**

### Étape 3: Redémarrer le serveur Odoo (si nécessaire)

```bash
# Dans votre terminal
cd d:\My_Work_Space\Odoo_19_v2
start_odoo_8070.cmd
```

## Configuration Initiale

### Créer un Programme Bon d'achat

1. Aller dans **Point de Vente → Produits → Remise & Fidélité**
2. Cliquer sur **Créer**
3. Sélectionner le template **Bon d'achat**
4. Configurer:
   - **Nom**: "Bons d'achat 2024" (par exemple)
   - **Date de début**: Date de début de validité (optionnel)
   - **Date de fin**: Date de fin de validité (optionnel)
   - Le reste est configuré automatiquement

### Générer des Bons d'achat

1. Ouvrir le programme créé
2. Cliquer sur **Générer des Coupons**
3. Remplir:
   - **Pour**: "Anonymous Customers" (clients anonymes)
   - **Montant du bon**: 50.00 (par exemple, pour un bon de 50€)
   - **Quantité**: 10 (nombre de bons à générer)
   - **Valable jusqu'au**: Date d'expiration (optionnel)
4. Cliquer sur **Générer**

### Consulter les Bons Générés

1. Dans le programme, cliquer sur **Bons d'achat** (smart button)
2. Vous verrez la liste des bons avec:
   - Code unique
   - État (Actif, Utilisé, Expiré)
   - Points (montant)
   - Date d'expiration

## Tests à Effectuer

### Test 1: Bon d'achat avec montant inférieur à la commande (T > A)

1. Ouvrir une session POS
2. Ajouter des produits pour un total de 100€
3. Cliquer sur le bouton **Bon d'achat**
4. Saisir un code de bon de 50€
5. **Résultat attendu**:
   - Message: "Bon d'achat appliqué: [CODE] / Montant déduit: 50,00 €"
   - Total de la commande: 50€ (100€ - 50€)
   - Ligne "Bon d'achat" de -50€ dans la commande
   - Le bon est marqué comme "Utilisé" en backend

### Test 2: Bon d'achat avec montant supérieur à la commande (T ≤ A)

1. Ouvrir une session POS
2. Ajouter des produits pour un total de 30€
3. Cliquer sur le bouton **Bon d'achat**
4. Saisir un code de bon de 50€
5. **Résultat attendu**:
   - Message: "Bon d'achat appliqué: [CODE] / Montant déduit: 30,00 €"
   - Total de la commande: 0€
   - Ligne "Bon d'achat" de -30€ dans la commande
   - Le bon est marqué comme "Utilisé" en backend (consommé totalement)

### Test 3: Réutilisation d'un bon (doit échouer)

1. Ouvrir une session POS
2. Créer une nouvelle commande
3. Cliquer sur le bouton **Bon d'achat**
4. Saisir le même code qu'au Test 1 ou 2
5. **Résultat attendu**:
   - Message d'erreur: "Ce bon d'achat a déjà été utilisé."
   - Aucune ligne ajoutée à la commande

### Test 4: Bon d'achat expiré

1. Dans le backend, modifier un bon pour définir une date d'expiration passée
2. Ouvrir une session POS
3. Cliquer sur le bouton **Bon d'achat**
4. Saisir le code du bon expiré
5. **Résultat attendu**:
   - Message d'erreur: "Ce bon d'achat a expiré."
   - Aucune ligne ajoutée à la commande

### Test 5: Code invalide

1. Ouvrir une session POS
2. Cliquer sur le bouton **Bon d'achat**
3. Saisir un code inexistant "INVALID123"
4. **Résultat attendu**:
   - Message d'erreur approprié
   - Aucune ligne ajoutée à la commande

### Test 6: Vérification Backend

Après chaque test, vérifier dans le backend:

1. Aller dans **Point de Vente → Produits → Remise & Fidélité**
2. Ouvrir le programme "Bons d'achat 2024"
3. Cliquer sur le smart button **Bons d'achat**
4. Vérifier pour le bon utilisé:
   - **État**: "Utilisé"
   - **Date d'utilisation**: Date et heure de l'utilisation
   - **Commande POS source**: Lien vers la commande POS
   - **Points**: 0 (consommé)
5. Ouvrir la commande POS liée
6. Vérifier l'historique de fidélité (si disponible)

### Test 7: Exclusion eCommerce (si module website_sale installé)

1. Aller sur le site web (eCommerce)
2. Ajouter des produits au panier
3. Essayer d'appliquer un code de bon d'achat
4. **Résultat attendu**:
   - Le code ne doit pas être reconnu ou accepté
   - Les programmes "Bon d'achat" ne doivent pas apparaître dans la liste des programmes disponibles

### Test 8: Ticket de caisse

1. Finaliser une commande avec un bon d'achat
2. Imprimer le ticket
3. **Résultat attendu**:
   - Ligne "Bon d'achat" clairement visible
   - Code du bon affiché
   - Montant déduit visible
   - Total correct après déduction

## Vérification de l'Installation

### Checklist Backend

- [ ] Programme "Bon d'achat" visible dans la liste des programmes
- [ ] Template "Bon d'achat" disponible lors de la création
- [ ] Wizard de génération affiche les messages en français
- [ ] Champs état, date d'utilisation, commande source visibles sur les bons
- [ ] Filtres "Bons d'achat actifs" et "Bons d'achat utilisés" fonctionnels

### Checklist POS

- [ ] Bouton "Bon d'achat" visible dans le panneau de contrôle
- [ ] Popup de saisie de code s'ouvre correctement
- [ ] Messages en français
- [ ] Application correcte du montant
- [ ] État mis à jour en temps réel
- [ ] Ligne de bon d'achat visible dans la commande

### Checklist Sécurité

- [ ] Utilisateurs POS peuvent lire et écrire les bons
- [ ] Managers POS ont accès complet
- [ ] Utilisateurs simples ont accès en lecture seule

## Dépannage

### Le bouton "Bon d'achat" n'apparaît pas

1. Vérifier qu'il existe au moins un programme de type "bon_achat" actif
2. Recharger la configuration POS (fermer et rouvrir la session)
3. Vider le cache du navigateur

### Erreur lors de la génération

1. Vérifier les logs Odoo
2. S'assurer que le programme est actif
3. Vérifier les permissions de l'utilisateur

### Le bon n'est pas marqué comme utilisé

1. Vérifier que la commande a été validée
2. Consulter les logs backend pour erreurs
3. Vérifier que le module pos_bon_achat est bien installé

### Messages non traduits

1. Vérifier que la langue française est installée
2. Mettre à jour les traductions
3. Redémarrer le serveur Odoo

## Support

Pour toute question ou problème:

1. Consulter les logs: Paramètres → Technique → Logs
2. Vérifier l'état du bon dans le backend
3. Tester avec un bon fraîchement généré

## Désinstallation (si nécessaire)

1. Aller dans **Paramètres → Apps**
2. Rechercher "pos_bon_achat"
3. Cliquer sur **Désinstaller**
4. Confirmer la désinstallation

**Attention**: La désinstallation supprimera tous les programmes de type "bon_achat" et leurs bons associés.
