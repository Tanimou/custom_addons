# Guide d'Import des Dépenses Carburant

## Présentation

Le module **Custom Fleet Fuel Management** permet l'import massif de dépenses carburant via fichier XLSX. Cette fonctionnalité est particulièrement utile pour :

- Intégrer des relevés de compte de cartes carburant fournisseur
- Migrer des historiques de dépenses depuis d'autres systèmes
- Importer des données depuis des terminaux ou applications tierces

## Prérequis

### Droits d'accès

L'import de dépenses nécessite le groupe **Gestionnaire carburant** (`group_fleet_fuel_manager`).

### Format du fichier

- **Format** : XLSX (Excel 2007+)
- **Encodage** : UTF-8 recommandé pour les caractères spéciaux
- **Taille maximale** : Limitée par la configuration serveur Odoo (par défaut ~50 Mo)

> ⚠️ **Important** : Le format XLS (Excel 97-2003) n'est pas supporté.

---

## Structure du fichier XLSX

### Colonnes requises

| Colonne | Type | Description | Exemple |
|---------|------|-------------|---------|
| `card_number` | Texte | Numéro unique de la carte carburant (champ `card_uid`) | `FCA-0001` |
| `expense_date` | Date | Date de la dépense au format `YYYY-MM-DD` ou format Excel natif | `2024-12-01` |
| `amount` | Nombre | Montant total de la dépense en devise société | `75.50` |
| `liter_qty` | Nombre | Quantité de carburant en litres | `50.25` |

### Colonnes optionnelles

| Colonne | Type | Description | Comportement |
|---------|------|-------------|--------------|
| `station_name` | Texte | Nom de la station service | Crée un partenaire fournisseur si inexistant |
| `odometer` | Nombre | Relevé odomètre au moment de la dépense | Utilisé pour le calcul L/100km |
| `vehicle_plate` | Texte | Immatriculation du véhicule | Écrase le véhicule lié à la carte si spécifié |
| `driver_name` | Texte | Nom complet du conducteur | Recherche dans `hr.employee` |
| `notes` | Texte | Commentaires ou observations | Stocké en HTML dans le champ notes |
| `fuel_type` | Texte | Type de carburant (`petrol`, `diesel`, `electric`, `hybrid`, `other`) | Ignoré si non reconnu |

### Exemple de fichier

```
card_number | expense_date | amount | liter_qty | station_name      | odometer | notes
FCA-0001    | 2024-12-01   | 75.50  | 50.25     | Station TotalEnergies | 125430   | Plein complet
FCA-0001    | 2024-12-05   | 45.00  | 30.15     | Station Shell     | 125890   |
FCA-0002    | 2024-12-02   | 82.30  | 55.00     | Station Avia      | 89120    | Autoroute A6
```

---

## Procédure d'import

### Étape 1 : Créer un lot d'import

1. Aller dans **Carburant > Dépenses > Lots d'import**
2. Cliquer sur **Créer**
3. Donner un nom descriptif au lot (ex: "Import relevé décembre 2024")
4. Cliquer sur **Enregistrer**

### Étape 2 : Charger le fichier

1. Dans le lot créé, localiser le champ **Fichier**
2. Cliquer sur **Télécharger** et sélectionner votre fichier XLSX
3. Le nom du fichier s'affiche dans le champ **Fichier**

### Étape 3 : Lancer l'import

1. Cliquer sur le bouton **Importer**
2. L'état du lot passe à **En cours**
3. Attendre la fin du traitement (visible via le champ **Fin**)
4. L'état final sera **Terminé** ou **En erreur**

### Étape 4 : Vérifier les résultats

1. Consulter l'onglet **Lignes** du lot
2. Chaque ligne indique :
   - **Ligne** : Numéro de ligne dans le fichier Excel
   - **État** : `Créée`, `Ignorée` ou `Erreur`
   - **Message** : Détail du traitement ou de l'erreur
   - **Dépense liée** : Lien vers la dépense créée (si succès)

3. Les compteurs en haut du lot affichent :
   - **Nombre de lignes** : Total des lignes traitées
   - **Succès** : Dépenses créées avec succès
   - **Erreurs** : Lignes en erreur

### Étape 5 : Traiter les erreurs

1. Filtrer les lignes par état **Erreur**
2. Analyser le message d'erreur pour chaque ligne
3. Corriger le fichier source si nécessaire
4. Créer un nouveau lot pour réimporter les lignes corrigées

---

## Gestion des erreurs courantes

### Carte non trouvée

**Message** : `Carte carburant non trouvée: XXX`

**Cause** : Le numéro de carte dans la colonne `card_number` ne correspond à aucune carte dans le système.

**Solution** :
- Vérifier l'orthographe exacte du numéro de carte
- S'assurer que la carte existe et est active
- Créer la carte manquante avant de réimporter

### Carte inactive

**Message** : `Carte carburant inactive ou expirée: XXX`

**Cause** : La carte existe mais n'est pas en état `active`.

**Solution** :
- Activer la carte dans **Carburant > Cartes carburant**
- Ou importer les dépenses sur une période où la carte était active

### Montant invalide

**Message** : `Montant invalide ou négatif`

**Cause** : La colonne `amount` contient une valeur non numérique, négative ou nulle.

**Solution** :
- Vérifier le format des nombres (utiliser `.` comme séparateur décimal)
- S'assurer que tous les montants sont strictement positifs

### Date invalide

**Message** : `Format de date invalide`

**Cause** : La date n'est pas dans un format reconnu.

**Solution** :
- Utiliser le format `YYYY-MM-DD` (ISO 8601)
- Ou utiliser une cellule Excel au format date natif
- Éviter les formats localisés comme `DD/MM/YYYY`

### Doublon détecté

**Message** : `Dépense déjà importée (doublon)`

**Cause** : Une dépense avec les mêmes caractéristiques existe déjà.

**Solution** : C'est un comportement normal de déduplication. Voir section suivante.

---

## Règles de déduplication

### Mécanisme de hash

L'import utilise un **hash SHA-1** calculé sur les éléments suivants pour détecter les doublons :

```
hash = SHA1(card_id + expense_date + amount + liter_qty)
```

Si une dépense avec le même hash existe déjà, la ligne est ignorée avec le statut `Ignorée`.

### Cas particuliers

| Situation | Comportement |
|-----------|--------------|
| Même carte, même date, même montant, même litres | Ignoré (doublon) |
| Même carte, même date, montant différent | Importé (nouvelle dépense) |
| Même carte, date différente, même montant | Importé (nouvelle dépense) |
| Réimport du même fichier | Toutes les lignes ignorées |

### Forcer un nouvel import

Si vous devez réimporter une dépense existante (correction) :

1. Supprimer la dépense originale (si état `brouillon` ou `rejetée`)
2. Réimporter le fichier
3. Ou modifier légèrement un paramètre (ex: ajouter 0.01 au montant)

---

## Validation des dépenses importées

Les dépenses créées par import ont les caractéristiques suivantes :

- **État** : `brouillon` (draft)
- **Justificatif** : Non renseigné (à ajouter manuellement si requis)
- **Lot d'import** : Lié au lot source pour traçabilité

### Workflow post-import

1. **Vérifier** les dépenses importées dans **Carburant > Dépenses**
2. **Ajouter les justificatifs** si la configuration l'exige
3. **Soumettre** les dépenses pour validation
4. **Valider** les dépenses (déduction automatique du solde carte)

### Validation en masse

Pour valider plusieurs dépenses d'un coup :

1. Aller dans **Carburant > Dépenses**
2. Filtrer par **Lot d'import** = votre lot
3. Sélectionner toutes les dépenses (case à cocher)
4. Utiliser **Action > Soumettre** puis **Action > Valider**

---

## Intégration API

### Endpoint d'import programmatique

Pour les intégrations avec des systèmes externes, vous pouvez créer des lots d'import via l'API XML-RPC ou JSON-RPC d'Odoo.

#### Exemple Python (XML-RPC)

```python
import xmlrpc.client

url = 'http://localhost:8069'
db = 'ma_base'
username = 'admin'
password = 'admin'

# Authentification
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})

# Appel aux modèles
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Créer un lot d'import
batch_id = models.execute_kw(db, uid, password,
    'fleet.fuel.expense.batch', 'create',
    [{'name': 'Import API Décembre 2024'}]
)

# Créer des lignes de dépenses directement
expense_data = {
    'card_id': 1,  # ID de la carte
    'expense_date': '2024-12-15',
    'amount': 65.00,
    'liter_qty': 43.50,
    'batch_id': batch_id,
}
expense_id = models.execute_kw(db, uid, password,
    'fleet.fuel.expense', 'create',
    [expense_data]
)

print(f"Dépense créée: {expense_id}")
```

#### Exemple cURL (JSON-RPC)

```bash
# Authentification
curl -X POST http://localhost:8069/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "common",
      "method": "authenticate",
      "args": ["ma_base", "admin", "admin", {}]
    },
    "id": 1
  }'

# Créer une dépense
curl -X POST http://localhost:8069/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "service": "object",
      "method": "execute_kw",
      "args": [
        "ma_base", 2, "admin",
        "fleet.fuel.expense", "create",
        [{"card_id": 1, "expense_date": "2024-12-15", "amount": 65.0, "liter_qty": 43.5}]
      ]
    },
    "id": 2
  }'
```

### Webhook pour import automatique

Pour une intégration temps réel avec un fournisseur de cartes carburant :

1. Créer un contrôleur HTTP dans un module personnalisé
2. Recevoir les notifications du fournisseur
3. Appeler la méthode `create` du modèle `fleet.fuel.expense`
4. La déduplication par hash évite les doublons automatiquement

---

## Bonnes pratiques

### Avant l'import

- [ ] Vérifier que toutes les cartes référencées existent
- [ ] S'assurer que les cartes sont en état `active`
- [ ] Valider le format des dates et nombres dans Excel
- [ ] Supprimer les lignes vides ou d'en-tête en fin de fichier

### Pendant l'import

- [ ] Ne pas fermer la fenêtre pendant le traitement
- [ ] Pour les gros fichiers (>1000 lignes), prévoir du temps de traitement
- [ ] Surveiller les logs serveur en cas de problème

### Après l'import

- [ ] Vérifier le ratio succès/erreurs
- [ ] Analyser et corriger les lignes en erreur
- [ ] Ajouter les justificatifs manquants
- [ ] Valider les dépenses avant la clôture mensuelle

---

## FAQ

### Puis-je importer des dépenses sur des cartes expirées ?

Non, seules les cartes en état `active` acceptent de nouvelles dépenses. Pour importer un historique, vous devez temporairement réactiver la carte.

### Comment annuler un import ?

Vous pouvez supprimer les dépenses créées si elles sont encore en état `brouillon`. Utilisez le filtre par lot d'import pour les identifier facilement.

### L'import prend en compte les plafonds de carte ?

L'import crée les dépenses mais ne les valide pas automatiquement. Le contrôle des plafonds s'effectue lors de la validation de chaque dépense.

### Puis-je importer dans une devise différente ?

Non, l'import utilise automatiquement la devise de la société. Convertissez les montants avant l'import si nécessaire.

### Comment importer des dépenses sans litre (ex: péage) ?

Mettez `0` dans la colonne `liter_qty`. Le champ est requis mais accepte la valeur zéro pour les dépenses non-carburant.

---

## Support

Pour toute question sur l'import de dépenses :

1. Consulter les logs du lot d'import (champ **Journal**)
2. Vérifier les messages d'erreur dans l'onglet **Lignes**
3. Contacter l'équipe support avec le fichier source et les logs
