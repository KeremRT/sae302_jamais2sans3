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
