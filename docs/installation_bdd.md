# Installation de la base et utilisation — Huy-Ming

Contribution : scénarios reproductibles et stockage MariaDB. Les fichiers de Kerem dans `sae302_Jamais2sans3/` et le dossier `serveur/` restent inchangés.

## Installation

Depuis la racine du dépôt, dans PowerShell :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r sql/requirements.txt
```

Dans le client MariaDB, avec un compte autorisé à créer la base :

```sql
SOURCE C:/chemin/du/depot/sql/schema.sql;
```

Ce script crée `sae302` et quatre tables InnoDB. Il ne migre pas une ancienne structure différente. Le compte utilisé par Python doit disposer de SELECT, INSERT et UPDATE sur cette base. L'administrateur crée ce compte séparément.

Créer un fichier **hors du dépôt**, par exemple `$HOME/sae302-prive.ini` :

```ini
[database]
host = 127.0.0.1
port = 3306
database = sae302
user = utilisateur_application
password = MOT_DE_PASSE_LOCAL
```

Adapter le port à l'installation. Ne jamais publier ce fichier ni le mot de passe.

## Scénarios et mesures

Les JSON décrivent les trajectoires, vitesses en pixels/s, positions d'entrée à zéro, horaires d'apparition et état initial des feux. S01 = urgence seule, S02 = normal, S03 = dense avec file devant l'ambulance. Chaque paire reprend exactement le même JSON ; seul le booléen de priorité change.

```powershell
# Mesurer sans base : JSON affiché dans le terminal
.\.venv\Scripts\python.exe scenarios/comparer_scenarios.py --scenario tous
# Importer les configurations et enregistrer les essais réels du simulateur
.\.venv\Scripts\python.exe scenarios/comparer_scenarios.py --scenario tous --config "$HOME/sae302-prive.ini"
```

Le script charge une instance isolée du moteur existant et lui fournit le calendrier en mémoire. Il ne réécrit aucun fichier et n'ajoute pas de menu à l'interface. Son exécution est séquentielle. `scenario_version=3` distingue ces configurations des essais précédents. Une modification des paramètres nécessite une nouvelle version.

## Tables et intégration

- `scenarios` : clé `(scenario_id, scenario_version)`, configuration JSON et empreinte SHA-256.
- `comparisons` : UUID d'une paire, copie des paramètres, origine `SIMULATION` ou `EXEMPLE` ; référence au scénario.
- `trials` : UUID de chaque essai, mode, état, départ, arrivée, durée ; référence à la comparaison et unicité `(comparison_id, mode)`.
- `events` : UUID unique, temps simulé et contenu ; référence à l'essai, retransmissions dédupliquées.

`sql/sae_data/` fournit `MesuresRepository`. La séquence est : `creer_comparaison`, `ouvrir_essai` pour SANS/AVEC, puis `traiter_evenement` pour `trial_started`, `priority_departed`, `priority_arrived` ou `trial_interrupted`. Les UUID et la version relient chaque message au bon essai. `lire_comparaison` ne fournit un gain que si les deux essais sont terminés. Chaque événement et la mise à jour de son essai sont validés dans une même transaction ; une paire peut rester incomplète si l'exécution est interrompue.

Ce raccordement est validé avec le script de comparaison. Le raccordement à l'interface de Kerem et au serveur de Youssef reste à faire avec eux. Aucun fichier du serveur n'est modifié. Un accusé de réception réseau ne devra être envoyé qu'après confirmation de la sauvegarde.

## Données fictives et tests

`sql/donnees_test.sql` contient une paire **EXEMPLE**, avec 18 s sans et 15 s avec, soit +3 s. Exécuter une seule fois dans une base de test sélectionnée, après création du même schéma. En cas d'erreur, faire ROLLBACK et ne pas poursuivre au COMMIT. Ces valeurs ne sont pas les mesures de l'application. `sql/demo.py` permet aussi de créer des exemples explicitement étiquetés.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s scenarios -v
$env:PYTHONPATH = (Resolve-Path sql).Path
.\.venv\Scripts\python.exe -m unittest discover -s sql/tests_data -v
```

Sans `SAE_TEST_CONFIG`, les tests de données utilisent SQLite et trois tests MariaDB sont ignorés. Pour tout vérifier sur MariaDB, préparer une **base distincte de `sae302`** avec les mêmes tables (adapter uniquement CREATE DATABASE et USE dans une copie de `schema.sql`) et une configuration privée :

```powershell
$env:SAE_TEST_CONFIG = "$HOME/sae302-test-prive.ini"
.\.venv\Scripts\python.exe -m unittest discover -s sql/tests_data -v
Remove-Item Env:SAE_TEST_CONFIG
Remove-Item Env:PYTHONPATH
```

Les tests ajoutent des données EXEMPLE dans la base de test ; ils ne suppriment pas les données existantes. `sql/lire_resultats.sql` fournit les requêtes de consultation. Les unités sont des secondes simulées, jamais le temps d'exécution de l'ordinateur.
