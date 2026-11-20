# SAÉ 3.02 — Carrefour intelligent — Jamais2sans3

Application pédagogique de BUT Réseaux et Télécommunications : simulation d'un carrefour à cinq branches, priorité à une ambulance, communication TCP/JSON et stockage MariaDB. Aucun équipement routier réel n'est commandé.

## Équipe

| Membre | Partie principale |
|---|---|
| Kerem Karaaslan | Interface graphique et moteur de simulation |
| Youssef Allag | Serveur TCP, client réseau et stratégie de priorité |
| Huy-Ming Banchongphanith | Scénarios, base MariaDB et résultats |

Le groupe comprend trois étudiants. Le nom du groupe est **Jamais2sans3**.

## Version et prérequis

Ces instructions concernent le projet regroupé : `main.py`, `serveur_central.py`, ce README et `requirements.txt` sont dans le même dossier. Pour le rendu GitHub, publier le **contenu** de ce dossier à la racine du dépôt. Les anciennes versions placées dans des sous-dossiers sur d'autres branches ne suivent pas cette organisation.

Prévoir Git et Python 3.12 ou 3.13 sur Windows 11. Le serveur utilise Debian 13, Python 3 et MariaDB. La fenêtre graphique s'exécute sur Windows. Les deux machines doivent communiquer sur le port TCP 5000 ; adapter l'adresse du serveur à votre réseau.

Dépendances Python : PySide6 pour l'interface et PyMySQL pour MariaDB. Elles sont listées dans `requirements.txt`.

## 1. Récupérer le projet

Une fois la version regroupée publiée à la racine du dépôt, exécuter sur chaque machine :

```bash
git clone https://github.com/KeremRT/sae302_jamais2sans3.git
cd sae302_jamais2sans3
```

Si vous utilisez le ZIP regroupé avant publication, le décompresser et ouvrir un terminal dans `Projet_SAE302`, le dossier contenant `requirements.txt`. La suite est identique. Ne pas mélanger des fichiers provenant de plusieurs branches.

## 2. Installer sur Windows

Dans PowerShell, depuis le dossier du projet :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloque l'activation, utiliser directement l'interpréteur de l'environnement, sans changer la politique de sécurité :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dans ce cas, remplacer `python` par `.\.venv\Scripts\python.exe` dans les commandes Windows suivantes.

## 3. Installer le serveur Debian

```bash
sudo apt update
sudo apt install -y git python3 python3-venv mariadb-server
sudo systemctl enable --now mariadb
python3 -m venv .venv-debian
source .venv-debian/bin/activate
python -m pip install PyMySQL==1.1.2
```

PySide6 n'est pas nécessaire au serveur sans interface. Pour installer toutes les dépendances du projet dans cet environnement, utiliser `python -m pip install -r requirements.txt`. Ne pas copier l'environnement virtuel de Windows vers Debian.

## 4. Préparer MariaDB

Sur Debian, depuis le dossier du projet :

```bash
sudo mariadb < sql/01_schema.sql
sudo mariadb
```

Dans le client MariaDB, créer un compte applicatif en remplaçant le mot de passe :

```sql
CREATE USER IF NOT EXISTS 'sae_huyming'@'127.0.0.1'
IDENTIFIED BY 'REMPLACER_PAR_UN_MOT_DE_PASSE_PRIVE';
GRANT SELECT, INSERT, UPDATE ON sae302.* TO 'sae_huyming'@'127.0.0.1';
EXIT;
```

Si le compte existe déjà, conserver son mot de passe actuel : `CREATE USER IF NOT EXISTS` ne le remplace pas. Le schéma crée les tables sans effacer les données, mais ne migre pas une ancienne structure incompatible.

Placer la configuration hors du dépôt :

```bash
cp config.example.ini "$HOME/sae302-prive.ini"
chmod 600 "$HOME/sae302-prive.ini"
nano "$HOME/sae302-prive.ini"
```

Renseigner les valeurs correspondant à votre installation :

```ini
[database]
host = 127.0.0.1
port = 3306
database = sae302
user = sae_huyming
password = VOTRE_MOT_DE_PASSE_PRIVE
ssl_ca =
```

Ne jamais publier le fichier privé, les mots de passe, les environnements virtuels ou une copie de la base.

## 5. Lancer et utiliser l'application

### Mode réseau avec MariaDB

Sur Debian, avec l'environnement activé :

```bash
python serveur_central.py --host 0.0.0.0 --port 5000 --config "$HOME/sae302-prive.ini"
```

Sur Windows, remplacer l'adresse d'exemple par celle de Debian :

```powershell
python interface_reseau.py --host 192.168.56.101 --port 5000
```

1. Choisir S01, S02 ou S03 dans la liste.
2. Cliquer sur **Démarrer réseau** ou **Comparer via serveur TCP**.
3. L'application exécute SANS puis AVEC priorité sur le même scénario.
4. Le serveur décide des transitions des feux et sauvegarde les événements dans MariaDB.
5. La fenêtre affiche les durées et le gain relus dans la base.

Le bouton **Arrêter essai** demande une interruption ; il ne s'agit pas d'une pause reprenable. Un essai incomplet ne donne pas de gain comparable. Le gain est `durée SANS − durée AVEC` ; une valeur négative représente une perte de temps.

Pour réaliser les comparaisons réseau sans fenêtre :

```powershell
python client_reseau.py --host 192.168.56.101 --port 5000 --scenario tous
```

### Mode local sans réseau

```powershell
python main.py
```

Choisir un scénario, utiliser Démarrer/Pause/Recommencer et **Comparer le même scénario**. Ce mode utilise le contrôleur local et ne sauvegarde pas automatiquement dans MariaDB. Les temps peuvent différer du mode réseau, dont les transitions sont décidées par le serveur.

| Scénario | Situation |
|---|---|
| S01 | Ambulance seule |
| S02 | Trafic croisé |
| S03 | File de véhicules devant l'ambulance |

## Organisation

| Fichiers | Rôle |
|---|---|
| `main.py`, `simulation.py` | Interface locale et moteur partagé |
| `interface_reseau.py`, `client_reseau.py` | Interface réseau et échanges côté Windows |
| `serveur_central.py`, `priorite_simple.py` | Serveur Debian et décisions de priorité |
| `scenarios/`, `scenarios_loader.py` | Trois scénarios et validation de leur configuration |
| `sae_data/` | Connexion, validation, protocole JSON et stockage transactionnel |
| `sql/01_schema.sql`, `sql/02_lire_resultats.sql` | Création des tables et consultation des résultats |
| `executer_scenarios.py` | Comparaisons locales en ligne de commande, avec sauvegarde facultative |
| `demo.py` | Données fictives EXEMPLE, également utilisées par certains tests |
| `test_*.py`, `tests_data/` | Vérifications du moteur, des données et du réseau |

## Tests et limites des vérifications

Depuis la racine, avec l'environnement Python activé :

```bash
python -m unittest discover -v
python -m unittest discover -s tests_data -v
```

Les tests automatiques TCP utilisent une base SQLite temporaire. Les trois tests de concurrence MariaDB sont ignorés sans configuration dédiée. Ces tests locaux ne remplacent pas une démonstration complète entre Windows, Debian et MariaDB.

Pour vérifier MariaDB, préparer une **base distincte de `sae302`** avec les mêmes tables : dans une copie de `sql/01_schema.sql`, adapter CREATE DATABASE et USE au nom de la base de test. Donner les droits nécessaires à un compte de test et créer son fichier INI privé. Sur Debian :

```bash
export SAE_TEST_CONFIG="$HOME/sae302-test-prive.ini"
python -m unittest discover -s tests_data -v
unset SAE_TEST_CONFIG
```

Sous PowerShell, utiliser `$env:SAE_TEST_CONFIG = "$HOME/sae302-test-prive.ini"`, puis `Remove-Item Env:SAE_TEST_CONFIG` après les tests. Les tests ajoutent des données EXEMPLE ; ils ne doivent pas utiliser la base du rendu.

Pour vérifier manuellement les erreurs TCP, serveur déjà démarré :

```powershell
python test_erreurs_tcp.py --host 192.168.56.101 --port 5000
```

En cas d'échec de connexion, vérifier l'adresse, le port, le lancement du serveur et les règles du pare-feu. En cas de refus SQL, vérifier le compte MariaDB et le fichier INI côté Debian.

Le serveur traite une connexion cliente à la fois. Le modèle routier est simplifié. Les fichiers de scénario et le moteur doivent provenir de la même version sur les deux machines : le client actuel ne compare pas automatiquement son JSON avec celui du serveur.

## Documents du rendu

- [Bilan_Projet.pdf](Bilan_Projet.pdf) : bilan fonctionnel, technique et organisationnel existant.
- [IAGraphie.pdf](IAGraphie.pdf) : déclaration existante de l'utilisation de l'IA.
- [GUIDE_YOUSSEF.md](GUIDE_YOUSSEF.md) : compléments de configuration des VM ; pour les chemins et l'installation de cette version regroupée, suivre d'abord ce README.
- `docs/historique/` : documents des étapes précédentes, dont certaines instructions et mesures concernent d'autres versions.

Les PDF sont conservés sans modification dans cette mise à jour documentaire. Leur actualisation et l'ajout du comparatif entre planning prévu et temps réel restent à effectuer avant le rendu final.
