# SAÉ 3.02 — Carrefour intelligent (Jamais2sans3)

**V1 pédagogique — simulation locale**. Un seul carrefour à cinq branches, inspiré de la géométrie du carrefour situé près du Crédit Agricole / IUT à Colmar. Le dessin est volontairement schématique, hypothétique et ne reproduit pas la signalisation réelle.

## Installer sur Windows 11

Dans VS Code, ouvrir le dossier contenant `main.py`, puis dans le terminal PowerShell :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Si tu utilises déjà un dossier de projet avec un environnement `.venv` configuré, copie simplement `main.py` et `simulation.py` dans ce dossier, puis exécute la dernière commande.

## Fonctions incluses

- Vue 2D schématique à cinq branches, sans terre-plein central et sans zébrures inutiles.
- Cinq feux F1 à F5 (trois groupes : Est-Ouest, Nord-Sud, Sud-Ouest).
- Petits véhicules animés avec ligne d'arrêt et espacement sur une même trajectoire.
- Ambulance de l'ouest vers l'est, arrêt à son feu si nécessaire.
- Priorité automatique **simulée localement** : orange, tous rouges, priorité, retour sécurisé.
- Boutons Démarrer / Pause / Recommencer, choix de la priorité, vitesse d'animation.
- Comparaison reproductible du **même scénario** avec/sans coordination (temps simulé).
- Trajectoires secondaires affichables à la demande.

## Ce qui reste à réaliser

- Connecter le moteur au serveur TCP/JSON de Youssef : pour l'instant la décision de priorité est **locale**, il n'existe pas de communication réseau.
- Raccorder le serveur TCP de Youssef au module MariaDB. Les scénarios S01/S02/S03 v2 et la sauvegarde directe en ligne de commande sont maintenant disponibles ; l’interface seule n’écrit pas en base.
- Étendre les trajectoires et vérifier les conflits de mouvements réels : ce prototype ne modélise qu'une partie des mouvements possibles ; il n'est pas adapté à la régulation routière réelle.
- Ajouter éventuellement le tramway comme **décor fixe uniquement**, comme décidé par le groupe.
- Construire le jeu de tests complet et la documentation finale.

## Organisation du code

- `main.py` : dessin et interface graphique PySide6, boutons, chronos, états visibles.
- `simulation.py` : trajectoires, véhicules, feux, logique de priorité et calcul de comparaison, sans dépendance à Qt.
- `test_simulation.py` : tests minimaux automatisés.

## Ce qui est mesuré

La durée simulée entre l’entrée effective du centre de l’ambulance et l’arrivée de ce même point à la fin du trajet. La durée est arrivée moins départ ; l’attente éventuelle hors de la zone est journalisée mais exclue de cette durée. `DT=0.05 s` est le pas fixe de calcul ; le sélecteur de vitesse agit sur l'affichage, **pas** sur le temps mesuré. Les conditions initiales et les autres véhicules sont les mêmes pour les deux essais ; la seule différence est la coordination des feux.

**Important :** la priorité simulée et les durées de feux sont des hypothèses pédagogiques ; aucune commande de feu de circulation réel n'est prévue.

## Scénarios de Huy-Ming intégrés

Choisir S01 (ambulance seule), S02 (trafic croisé) ou S03 (file devant ambulance)
dans le sélecteur. Changer de scénario ou de mode réinitialise l’essai et les résultats.
Les fichiers `scenarios/` sont en **version 2**, adaptés aux cinq branches et à
l’ambulance Ouest vers Est de ce moteur. Les anciens scénarios v1 ont été retirés ; seules les configurations de `scenarios/` sont conservées.

### Exécuter sans interface

```powershell
.\.venv\Scripts\python.exe executer_scenarios.py --scenario tous
```

Le résultat JSON contient les configurations, UUID, événements, entrées effectives,
durées et gains, dans `resultats_locaux/comparaisons.json`. Ce fichier est local
et ignoré par Git. Les événements suivent le contrat v1, véhicule `A1`, limite
120 secondes. Les essais incomplets n’ont pas de gain final.

### Sauvegarder et relire dans MariaDB

1. Installer MariaDB séparément et exécuter `sql/01_schema.sql` avec le compte
   d’installation. Il crée `sae302` et les tables sans effacer les données ; il ne
   migre pas une ancienne structure différente.
2. Créer un utilisateur d’application et lui attribuer SELECT, INSERT et UPDATE
   sur cette base. Conserver le mot de passe localement.
3. Copier `config.example.ini` vers `config.ini` et renseigner les accès et le port.
4. Exécuter :

```powershell
.\.venv\Scripts\python.exe executer_scenarios.py --scenario tous --config config.ini
```

Chaque paire est sauvegardée comme `SIMULATION` et relue pour vérifier le gain.
Il s’agit de résultats du moteur local pédagogique, pas de mesures sur route,
ni d’une validation de la commande TCP des feux. Le contrôle reste local.
Les anciens jeux artificiels restent disponibles via `demo.py --scenario S02`
avec l’origine `EXEMPLE` : ils ne doivent pas être mélangés aux mesures v2.

### Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m unittest discover -s tests_data -v
```

La seconde commande utilise SQLite par défaut et ignore les trois tests de
concurrence MariaDB. Pour tester MariaDB, préparer une **base distincte** avec le
même schéma (adapter CREATE DATABASE et USE dans une copie du script SQL), puis
renseigner une configuration privée `config.test.ini` et lancer :

```powershell
$env:SAE_TEST_CONFIG = (Resolve-Path config.test.ini).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests_data -v
Remove-Item Env:SAE_TEST_CONFIG
```

Ne jamais publier `config.ini`, `config.test.ini`, les mots de passe ou `.venv`.
