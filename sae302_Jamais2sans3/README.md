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
- Intégrer la base MariaDB et les scénarios de Huy-Ming.
- Étendre les trajectoires et vérifier les conflits de mouvements réels : ce prototype ne modélise qu'une partie des mouvements possibles ; il n'est pas adapté à la régulation routière réelle.
- Ajouter éventuellement le tramway comme **décor fixe uniquement**, comme décidé par le groupe.
- Construire le jeu de tests complet et la documentation finale.

## Organisation du code

- `main.py` : dessin et interface graphique PySide6, boutons, chronos, états visibles.
- `simulation.py` : trajectoires, véhicules, feux, logique de priorité et calcul de comparaison, sans dépendance à Qt.
- `test_simulation.py` : tests minimaux automatisés.

## Ce qui est mesuré

Le temps simulé de l'ambulance entre son apparition et son arrivée à la fin du trajet. `DT=0.05 s` est le pas fixe de calcul ; le sélecteur de vitesse agit sur l'affichage, **pas** sur le temps mesuré. Les conditions initiales et les autres véhicules sont les mêmes pour les deux essais ; la seule différence est la coordination des feux.

**Important :** la priorité simulée et les durées de feux sont des hypothèses pédagogiques ; aucune commande de feu de circulation réel n'est prévue.


## Partie Huy-Ming : scénarios et base de données

- `scenarios/` : S01 ambulance seule, S02 trafic croisé, S03 file devant ambulance (v2, cinq branches, Ouest vers Est).
- `scenarios_loader.py` : lecture et validation de ces fichiers ; leur branchement au moteur et à l’interface reste à effectuer.
- `scenarios_v1/` : configurations initiales conservées pour les tests et la démonstration de la base.
- `sae_data/` : connexion MariaDB, validation des événements et enregistrement des comparaisons.
- `sql/` : création des tables et requêtes de lecture.
- `config.example.ini` : modèle à copier dans `config.ini` et à renseigner localement, sans publier les identifiants.
- `demo.py` : démonstration avec données artificielles marquées `EXEMPLE`, pas des résultats de simulation.
- `tests_data/` : tests du stockage et du protocole ; lancer `python -m unittest discover -s tests_data -v`. Les tests MariaDB nécessitent `SAE_TEST_CONFIG` pointant vers une configuration privée pour une base de test distincte.

Installer les dépendances avec `python -m pip install -r requirements.txt`. Pour préparer MariaDB, exécuter `sql/01_schema.sql` avec un compte autorisé, puis configurer un utilisateur applicatif disposant de SELECT, INSERT et UPDATE. L’interface et le moteur de Kerem ne sont pas modifiés par cet ajout ; leur connexion à ces fichiers et au serveur TCP reste à faire.
