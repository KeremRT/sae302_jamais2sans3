# Installation et utilisation — partie de Huy-Ming

## Les fichiers à comprendre

- `scenarios/scenario_*.json` : véhicules, horaires, directions, vitesses et feux au départ.
- `scenarios/comparer_scenarios.py` : lit le JSON, lance les deux essais et calcule le gain.
- `sql/base_donnees.py` : ouvre la connexion, enregistre la paire et relit les durées.
- `sql/schema.sql` : crée les tables ; `donnees_test.sql` ajoute des exemples fictifs.

Les fichiers de Kerem et le serveur de Youssef ne sont pas modifiés.

## Installation

Depuis la racine du dépôt :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r sql/requirements.txt
```

Dans MariaDB, avec un compte administrateur :

```sql
SOURCE C:/chemin/du/depot/sql/schema.sql;
```

Le script crée la base `sae302` et trois tables :

1. `scenarios` conserve les paramètres et leur version.
2. `comparisons` identifie une comparaison et référence son scénario.
3. `trials` conserve les deux essais SANS et AVEC, leurs temps et leurs états.

Les clés étrangères relient les tables. Un UUID est simplement un identifiant unique. L'empreinte SHA-256 permet de détecter si un scénario a changé : dans ce cas, augmenter `version` dans son JSON.

Le schéma reste compatible avec les tables déjà créées. L'ancienne table `events`, si elle existe, n'est plus utilisée ; aucune donnée ancienne n'est supprimée. Le programme simplifié sauvegarde une paire complète dans une transaction, pas les événements un par un.

Créer un utilisateur MariaDB avec SELECT, INSERT et UPDATE sur `sae302`. Placer sa configuration **hors du dépôt**, par exemple dans `$HOME/sae302-prive.ini` :

```ini
[database]
host = 127.0.0.1
port = 3306
database = sae302
user = votre_utilisateur
password = votre_mot_de_passe
```

Adapter le port à votre installation. Ne pas publier ce fichier.

## Exécution

```powershell
# Comparer sans enregistrer en base
.\.venv\Scripts\python.exe scenarios/comparer_scenarios.py --scenario tous
# Comparer puis sauvegarder et relire dans MariaDB
.\.venv\Scripts\python.exe scenarios/comparer_scenarios.py --scenario tous --config "$HOME/sae302-prive.ini"
```

Remplacer `tous` par `normal`, `dense` ou `urgence` pour un seul scénario. Les résultats s'affichent en JSON. Le gain vaut durée SANS moins durée AVEC : il peut être négatif. `null` signifie qu'un essai n'est pas terminé.

Le moteur lit une constante `SCENARIO`. Le script la remplace temporairement en mémoire puis la rétablit avec `finally`. Aucun fichier de Kerem n'est réécrit. Ce script lance les essais l'un après l'autre ; il n'est pas prévu pour plusieurs simulations dans des threads simultanés. Les positions à l'apparition sont toujours le début du trajet, à zéro pixel.

## Vérifications

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s scenarios -v
.\.venv\Scripts\python.exe sql/test_bdd.py --config "$HOME/sae302-test-prive.ini"
```

Pour le deuxième test, utiliser une base dont le nom contient `test` ou `validation`, avec les mêmes tables. Pour la créer, adapter CREATE DATABASE et USE dans une copie de `schema.sql`. La configuration de test reste hors du dépôt. Le test ajoute des exemples fictifs et vérifie relecture, gain négatif, essai incomplet et annulation d'une sauvegarde incorrecte.

`sql/donnees_test.sql` peut aussi être exécuté dans cette base de test : il contient 18 s et 15 s, étiquetés EXEMPLE. `sql/lire_resultats.sql` permet de consulter les mesures.

Le raccordement à l'interface et au serveur reste un travail commun. Avec cette version simple, une fermeture brutale du script avant la sauvegarde ne laisse aucune paire enregistrée. Un dépassement de la durée maximale est enregistré comme INTERROMPU si la sauvegarde est demandée.
