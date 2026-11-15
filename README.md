# SAÉ 3.02 — Carrefour intelligent

## Présentation du projet

Projet réalisé dans le cadre du BUT 2 Réseaux et Télécommunications à l'IUT de Colmar, Université de Haute-Alsace.

**Nom du groupe : Jamais2sans3**

Ce projet consiste à développer une simulation informatique d'un carrefour intelligent permettant d'étudier la circulation des véhicules et le passage d'un véhicule prioritaire.

Notre application représente un carrefour schématique à cinq branches, inspiré d'une intersection de Colmar.

L'objectif est de comparer le temps de passage d'une ambulance dans deux situations :
- Sans système de priorité.
- Avec un système de priorité simulé.

Le projet constitue un prototype pédagogique et ne commande pas de véritables équipements routiers.

## Membres du groupe

| Membre | Contribution principale |
|---|---|
| Kerem Karaaslan | Interface graphique, moteur de simulation et tests |
| Youssef [NOM À COMPLÉTER] | Serveur, communication TCP et gestion des priorités |
| Huy-Ming [NOM À COMPLÉTER] | Scénarios de circulation, base de données MariaDB et tests |

## Technologies utilisées

- Python : langage principal du projet.
- PySide6 : développement de l'interface graphique.
- TCP / JSON : technologies utilisées pour la partie communication réseau.
- MariaDB : stockage des données et des résultats.
- PyMySQL : communication entre Python et MariaDB.
- Git et GitHub : gestion des versions et collaboration.

## Fonctionnalités de la simulation

La partie graphique du projet comprend :

- Un carrefour schématique à cinq branches.
- Cinq feux de circulation (F1 à F5).
- Une simulation du déplacement des véhicules.
- La circulation d'une ambulance.
- Une gestion des phases des feux.
- Un mode avec et sans priorité simulée.
- Une comparaison des temps de passage.
- Les boutons Démarrer, Pause et Recommencer.
- Des tests automatisés du moteur de simulation.

Les modules serveur, scénarios et MariaDB sont également présents dans le dépôt. Leur intégration complète avec l'interface doit être validée par des tests avant d'être considérée comme fonctionnelle.

## Prérequis

Pour utiliser l'application sous Windows :

- Windows 10 ou Windows 11.
- Python 3.12.
- Git.
- Une connexion Internet pour installer les dépendances.

MariaDB est nécessaire uniquement pour les fonctionnalités utilisant la base de données.

## Installation du projet

### 1. Cloner le dépôt GitHub

Ouvrir PowerShell et exécuter :

```powershell
git clone https://github.com/KeremRT/sae302_jamais2sans3.git
cd sae302_jamais2sans3
```

### 2. Créer un environnement virtuel Python

```powershell
py -3.12 -m venv .venv
```

### 3. Installer les dépendances

Depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cette commande installe les bibliothèques nécessaires à l'interface et au module SQL.

## Démarrer l'application

Depuis la racine du dépôt :

```powershell
.\.venv\Scripts\python.exe .\sae302_Jamais2sans3\main.py
```

Une fenêtre graphique s'ouvre et affiche le carrefour.

## Guide d'utilisation

1. Lancer l'application.
2. Observer les différentes entrées du carrefour.
3. Choisir le fonctionnement avec ou sans priorité ambulance.
4. Cliquer sur Démarrer pour lancer la simulation.
5. Observer le déplacement des véhicules et les changements des feux.
6. Cliquer sur Pause pour suspendre la simulation.
7. Utiliser Recommencer pour relancer le scénario.
8. Comparer les temps de passage simulés.

## Exécuter les tests

Pour lancer les tests du moteur de simulation :

```powershell
.\.venv\Scripts\python.exe .\sae302_Jamais2sans3\test_simulation.py
```

Les tests vérifient notamment :
- Les cinq entrées du carrefour.
- La compatibilité des états des feux.
- La reproductibilité des comparaisons.
- L'espacement des véhicules dans les scénarios testés.
- Le comportement de l'ambulance au feu rouge.

## Structure du dépôt

```text
sae302_jamais2sans3/
|
|-- README.md
|-- requirements.txt
|-- Bilan_Projet.pdf
|-- IAGraphie.pdf
|
|-- sae302_Jamais2sans3/
|   |-- main.py
|   |-- simulation.py
|   |-- test_simulation.py
|   |-- requirements.txt
|
|-- serveur/
|-- scenarios/
|-- sql/
|-- docs/
```

Les fichiers Bilan_Projet.pdf et IAGraphie.pdf correspondent aux documents de remise à ajouter lors de la finalisation du projet.

## Partie serveur et communication

Le dossier serveur/ regroupe le travail consacré aux communications réseau et à la gestion centralisée des priorités.

Le fonctionnement de ce module doit être vérifié séparément, puis avec la simulation graphique.

## Partie base de données

Le dossier sql/ regroupe les scripts et les modules permettant de gérer les données du projet.

Les scénarios de circulation sont présents dans le dossier scenarios/.

Les instructions complémentaires sont disponibles dans docs/installation_bdd.md.

Ne jamais publier de véritables identifiants ou mots de passe MariaDB dans le dépôt.

## Documentation du projet

Le dépôt comprend également des documents d'analyse :

- Bilan_Projet.pdf : bilan fonctionnel, difficultés, organisation et comparaison du planning.
- IAGraphie.pdf : utilisation des intelligences artificielles génératives durant le projet.

## Limites du système

Le projet est une simulation pédagogique.

L'interface applique actuellement une logique locale de gestion des feux. La présence des modules serveur et SQL ne garantit pas leur interconnexion complète.

Le prototype ne doit pas être utilisé pour commander des feux réels. Une utilisation sur voie publique nécessiterait des dispositifs de sécurité, des validations réglementaires et des tests supplémentaires.

## Conclusion

Ce projet nous permet de mettre en pratique les compétences acquises en programmation Python, simulation, réseaux, bases de données et travail collaboratif.

Il illustre comment un système informatique pourrait contribuer à améliorer la circulation d'un véhicule prioritaire, dans les limites d'un environnement de simulation.
