# Guide de lancement complet — SAÉ 3.02 

**Objectif :** permettre à un autre étudiant de relancer le projet en **téléchargeant le fichier ZIP, en le décompressant sur Windows et Debian puis en installant les logiciels nécessaires**, sans passer par GitHub ni connaître nos VM. Ce guide correspond aux fichiers de la version intégrée **Kerem + Huy-Ming + Youssef** : cinq branches, trois scénarios v2, contrôle des feux par TCP et enregistrement MariaDB.

> Ce projet est une simulation pédagogique. Les états des feux et le contrôle du carrefour ne sont pas des dispositifs de sécurité pour une intersection réelle.

## 0. Identifier les trois parties

| Partie | Fichiers principaux | Ce qu'elle fait |
| --- | --- | --- |
| Simulation/affichage **Kerem** | `main.py`, `simulation.py` | Affiche le carrefour, les véhicules et l'ambulance ; moteur local conservé |
| Scénarios et SQL **Huy-Ming** | `scenarios/`, `scenarios_loader.py`, `sae_data/`, `sql/` | Décrit les scénarios S01/S02/S03, valide les mesures et sauvegarde les essais |
| Réseau et priorité **Youssef** | `serveur_central.py`, `priorite_simple.py`, `client_reseau.py`, `interface_reseau.py` | Reçoit des données TCP sur Debian, renvoie des commandes de feux et relie les deux parties |

- **`main.py` :** mode local, fonctionne sans Debian/MariaDB.
- **`client_reseau.py` :** test réseau en console, affiche les résultats et les commandes.
- **`interface_reseau.py` :** reprend l'interface Qt de Kerem et utilise le serveur Debian.
- **`serveur_central.py` :** tourne sur Debian ; `priorite_simple.py` doit être **dans le même dossier**.

Le serveur simplifié gère **un client TCP à la fois**. L'interface conserve un `QThread` : elle reste utilisable pendant l'attente réseau. Les UUID identifient les essais en base SQL et n'ont pas besoin d'être saisis manuellement.

## 1. Matériel et logiciels nécessaires

Deux VM sous VirtualBox (elles peuvent être sur le même ordinateur) :

- **Windows 11 :** installer **Python 3.14 (64 bits)**, VS Code (facultatif) et **OpenSSH Client** (commande `scp`) pour transférer le ZIP. Les essais du groupe ont utilisé Python 3.14.10.
- **Debian 13 :** Python 3, `python3-venv`, MariaDB, `openssh-server` et `unzip`.
- **Réseau :** une carte **NAT** sur chaque VM pour Internet et une carte **Réseau privé hôte / Host-only** sur les deux VM pour communiquer entre elles. Les deux machines doivent se trouver sur le même sous-réseau privé.

### 1.A. Configurer les deux cartes réseau dans VirtualBox

Éteindre les VM avant de modifier les paramètres VirtualBox. Pour **chacune** des deux VM, ouvrir **Configuration → Réseau** :

| Carte | Mode VirtualBox | Rôle |
| --- | --- | --- |
| Une carte | **NAT** | Accès à Internet (installation des dépendances) |
| L'autre | **Réseau privé hôte / Host-only** | Communication directe entre les deux VM |

Vérifier que **« Activer l'interface réseau »** et **« Câble branché »** sont cochés. Les cartes peuvent être inversées : **NAT peut être la carte 1 ou 2**, ce n'est pas une erreur.

### 1.B. Mettre en DHCP la carte Debian qui n’a pas d’adresse IP

Sur **Debian 13**, afficher les interfaces :

```bash
ip -br a
```

Repérer la carte qui n'a **pas d'adresse IPv4**, puis ouvrir le fichier réseau en administrateur :

```bash
su -
nano /etc/network/interfaces
```

**Ne pas supprimer les lignes déjà présentes.** Ajouter simplement les deux lignes `auto` et `iface` pour **la carte qui manque**. Par exemple, si `enp0s3` est déjà configurée et que `enp0s8` n'a pas d'adresse, le fichier devient :

```ini
source /etc/network/interfaces.d/*

auto lo
iface lo inet loopback

auto enp0s3
iface enp0s3 inet dhcp

auto enp0s8
iface enp0s8 inet dhcp
```

Ici, **les deux seules lignes à ajouter** sont :

```ini
auto enp0s8
iface enp0s8 inet dhcp
```

![Fichier /etc/network/interfaces dans Nano sous Debian](docs/images/debian_interfaces_dhcp.png)

Le nom de la carte peut être différent : utiliser celui affiché par `ip -br a`. Pour une carte **Host-only**, le serveur DHCP doit être activé dans VirtualBox ; la carte **NAT** reçoit normalement son IP automatiquement.

Dans Nano, enregistrer avec **Ctrl + O**, **Entrée**, puis quitter avec **Ctrl + X**. Redémarrer Debian :

```bash
reboot
```

Après le redémarrage, vérifier que les cartes ont une adresse IP :

```bash
ip -br a
ip route
```

La route par défaut doit passer par la carte NAT. Si l'adresse IP manque encore, vérifier le type de carte dans VirtualBox et que l'interface est bien gérée via `/etc/network/interfaces`.

### 1.C. Relever les adresses utilisées pour la communication TCP

| VM | Carte | IP d'exemple (à adapter) |
| --- | --- | --- |
| Debian 13 | Host-only | `192.168.56.109` |
| Windows 11 | Host-only | `192.168.56.107` |
| Debian 13 | NAT (DHCP) | `10.0.3.15` (**pas** l'IP du serveur à saisir dans Windows) |

Sur **Debian**, relever l'IP avec `ip -br a` ; sur **Windows**, ouvrir PowerShell et utiliser `ipconfig`. Les deux IP Host-only doivent se trouver sur le même réseau, par exemple `192.168.56.0/24`.

**Toutes les adresses `192.168.56.109` et `192.168.56.107` figurant dans ce guide sont des exemples : les remplacer par les IP réellement affichées sur les VM de l'étudiant.** Ne pas exposer l'application directement à Internet.

**À retenir pour la connexion TCP : l'adresse IP indiquée dans ce guide (par exemple `192.168.56.109`) sert uniquement à illustrer les commandes. Il faut utiliser l'adresse IPv4 réellement obtenue sur la carte Host-only de la VM Debian, affichée par `ip -br a` sur Debian.** Ne pas copier automatiquement l'adresse de l'exemple, car elle peut changer d'une VM à l'autre. Ce n'est **ni l'IP de la VM Windows**, ni l'IP NAT de Debian (`10.0.x.x`), ni l'adresse `127.0.0.1` du fichier `config.ini` (qui sert uniquement à MariaDB sur Debian).


### 1.D. Autoriser le ping et vérifier la communication entre les deux VM (pare-feu Windows)

**Faire cette vérification maintenant, avant le transfert des fichiers, les installations Python/MariaDB et le lancement du serveur.** Elle permet de confirmer que les deux VM peuvent communiquer via leur réseau privé hôte (Host-only).

Cette manipulation est à réaliser dans **la VM Windows 11** et non sur le PC physique. Sur un réseau VirtualBox, le pare-feu peut bloquer les demandes de ping venant de Debian. **Ne pas désactiver le pare-feu et ne pas créer de nouvelle règle : utiliser celle qui existe déjà.**

1. Sur Windows 11, rechercher **Panneau de configuration** puis ouvrir **Système et sécurité → Pare-feu Windows Defender**.
2. À gauche, cliquer sur **Paramètres avancés** pour ouvrir **Pare-feu Windows Defender avec fonctions avancées de sécurité**. Si cette fenêtre est déjà ouverte, passer à l'étape suivante.
3. Dans le menu de gauche, cliquer sur **Règles de trafic entrant**.

![Fenêtre des paramètres avancés du pare-feu Windows : accès aux règles de trafic entrant](docs/images/pare_feu_windows_avance.png)

4. Dans la liste, rechercher la règle **Partage de fichiers et d’imprimantes (Demande d’écho – Trafic entrant ICMPv4)**. Il existe parfois plusieurs règles pour les profils **Domaine**, **Privé** et **Public** : choisir le profil correspondant à la carte Host-only de VirtualBox (souvent **Public**).
5. Faire **clic droit → Activer la règle**, ou sélectionner la règle puis cliquer sur **Activer la règle** dans le panneau de droite. Si le menu propose **Désactiver la règle**, elle est déjà active.

![Liste des règles entrantes et option Activer la règle](docs/images/pare_feu_windows_regle_icmp.png)

**Important : sur la capture, la ligne surlignée est une règle ICMPv6, alors que celle à activer pour nos adresses `192.168.56.x` est bien la règle ICMPv4.** Sélectionner la bonne ligne avant de cliquer sur **Activer la règle**.

Pour limiter l'autorisation aux seules connexions provenant de Debian, ouvrir les **Propriétés** de la règle ICMPv4, puis **Étendue → Adresses IP distantes → Ces adresses IP** et ajouter l'adresse Host-only de Debian (exemple `192.168.56.109`). Cela évite d'autoriser les pings provenant de tout le réseau. Aucun ajout de règle n'est nécessaire.

#### Tester les deux sens de communication

Sur **Debian** (remplacer l'IP par celle de la carte Host-only Windows trouvée avec `ipconfig`) :

```bash
ping -c 4 192.168.56.107
```

Sur **Windows** (remplacer l'IP par celle de la carte Host-only Debian obtenue avec `ip -br a`) :

```powershell
ping 192.168.56.109
```

**Résultat attendu :** les réponses `64 bytes from ...` sur Debian et `Réponse de ...` sur Windows, sans perte de paquets. Si le ping ne fonctionne pas, vérifier les deux adresses, le réseau Host-only partagé, le **profil** de la règle activée et que la règle concerne bien **ICMPv4**.

**Ne pas passer aux tests TCP tant que le réseau Host-only n'est pas correctement configuré.** Le ping vérifie ICMP ; plus loin, `Test-NetConnection` vérifie séparément le port TCP `5000`.

**À retenir :** cette activation sert à autoriser les requêtes de ping **Debian → Windows**. Pour la SAE, le client **Windows → Debian** utilise le port TCP `5000` du serveur Debian : il n'est normalement pas nécessaire d'autoriser le port `5000` en entrée sur Windows.

---

## 2. Télécharger, décompresser et copier le projet sur les deux VM (sans GitHub)

**Télécharger le fichier `Projet_SAE302_documente.zip` fourni avec le rendu**, puis le conserver sur Windows. Ce ZIP contient le projet complet : fichiers de Kerem, fichiers de Huy-Ming, partie réseau de Youssef, scénarios, scripts SQL et guides. **Il ne contient pas les environnements Python** (`.venv`) ni le mot de passe privé MariaDB : on les recrée plus loin.

### 2.A. Sur Windows 11 — Décompresser le ZIP

1. Ouvrir l'Explorateur de fichiers et aller dans **Téléchargements**.
2. Faire un clic droit sur `Projet_SAE302_documente.zip` → **Extraire tout**.
3. Dans le dossier extrait, repérer celui qui contient directement `main.py`, `simulation.py`, `serveur_central.py`, `priorite_simple.py` et `sql/`. Il s'appelle `Projet_SAE302`.
4. Copier le dossier **`Projet_SAE302`** dans **Documents\Sae**, en conservant ce nom. L'objectif est d'obtenir :

```text
Documents\Sae\Projet_SAE302\
├── main.py
├── simulation.py
├── serveur_central.py
├── priorite_simple.py
├── client_reseau.py
├── interface_reseau.py
├── requirements.txt
├── scenarios\
├── sae_data\
└── sql\
```

**Attention :** selon l'outil de décompression, il peut y avoir deux dossiers imbriqués `Projet_SAE302`. Utiliser le dossier qui contient directement `main.py` : ce fichier doit se trouver dans `Projet_SAE302`, et non dans `Projet_SAE302\Projet_SAE302`.

Pour vérifier dans **PowerShell Windows** (adapter le chemin si le dossier Documents est ailleurs) :

```powershell
cd "$HOME\Documents\Sae\Projet_SAE302"
dir main.py, serveur_central.py, priorite_simple.py, requirements.txt
```

Si le dossier `Projet_SAE302` existe déjà, **ne pas l'écraser** : garder une sauvegarde et tester d'abord le ZIP dans un dossier séparé.

### 2.B. Sur Debian 13 — Activer le transfert de fichiers

Dans un terminal de **Debian**, vérifier l'IP de sa carte Host-only puis installer le service SSH et le décompresseur :

```bash
ip -br a
sudo apt update
sudo apt install -y openssh-server unzip
sudo systemctl enable --now ssh
```

Dans notre exemple, Debian a l'adresse `192.168.56.109` et l'utilisateur s'appelle `toto`. Remplacer **l'adresse et le nom d'utilisateur** si la VM de l'autre étudiant est différente.

### 2.C. Depuis Windows — Envoyer le ZIP à Debian

Ouvrir **PowerShell sur Windows 11** dans le dossier **Téléchargements** (ou là où le ZIP a été enregistré) :

```powershell
scp .\Projet_SAE302_documente.zip toto@192.168.56.109:/home/toto/
```

À la première connexion, accepter la clé SSH si l'adresse est bien celle de la VM Debian ; saisir ensuite le **mot de passe de l'utilisateur Debian** (il ne s'affiche pas pendant la saisie). Sous Windows 11, la commande `scp` fait partie d'OpenSSH Client : si elle est introuvable, activer **Client OpenSSH** dans les fonctionnalités facultatives de Windows.

### 2.D. Sur Debian — Décompresser le ZIP

Dans le terminal **Debian 13** :

```bash
cd ~
unzip Projet_SAE302_documente.zip
cd ~/Projet_SAE302
ls main.py serveur_central.py priorite_simple.py sql/01_schema.sql
```

Ces commandes supposent qu'il **n'existe pas déjà** de dossier `~/Projet_SAE302`. Si ce dossier existe, sauvegarder les données existantes et décompresser le ZIP dans un autre emplacement pour éviter de les écraser.

**À ce stade :** les deux VM possèdent les mêmes fichiers de code. Il reste à installer Python, MariaDB, les dépendances et le fichier de configuration privé : voir les étapes 3 à 9.

### 2.E. Cas particulier — Mettre à jour les VM qui fonctionnent déjà

Si le projet est déjà installé sur Windows et Debian, il n'est **pas nécessaire** de décompresser tout le projet par-dessus l'ancien, ni de réinstaller la base de données.

1. Faire une sauvegarde de `Projet_SAE302` sur Windows et de `~/Projet_SAE302` sur Debian.
2. Sur Windows, copier depuis le ZIP uniquement les fichiers réseau modifiés : `client_reseau.py`, `interface_reseau.py`, `serveur_central.py`, `priorite_simple.py`.
3. Sur Debian, arrêter le serveur avec `Ctrl+C` ; ne pas toucher à `config.ini` ni aux tables MariaDB.
4. Depuis **Windows**, dans `Documents\Sae\Projet_SAE302`, envoyer les deux fichiers nécessaires au serveur :

```powershell
scp .\serveur_central.py .\priorite_simple.py toto@192.168.56.109:/home/toto/Projet_SAE302/
```

5. Sur **Debian**, relancer le serveur après vérification des deux fichiers :

```bash
cd ~/Projet_SAE302
ls -l serveur_central.py priorite_simple.py
./.venv-debian/bin/python serveur_central.py --host 0.0.0.0 --port 5000 --config config.ini
```

Cette mise à jour **n'efface aucune table MariaDB**. `main.py`, `simulation.py`, `sae_data/`, `scenarios/` et `sql/` sont conservés.

## 3. Installer Python sur Windows 11

**Installer obligatoirement Python 3.14 sur la VM Windows 11 avant de créer l’environnement virtuel et d’exécuter le projet.**

1. Sur **la VM Windows 11**, ouvrir **PowerShell** (menu Démarrer → taper `PowerShell`).
2. Installer **Python 3.14** avec cette commande :

```powershell
winget install --id Python.Python.3.14 --exact
```

3. Accepter les éventuelles conditions d'installation. Si `winget` n'est pas reconnu, télécharger Python 3.14 (64 bits) depuis https://www.python.org/downloads/windows/ et lancer l'installateur ; cocher **Add Python to PATH** si cette option est proposée.
4. **Fermer puis rouvrir PowerShell**, puis vérifier la version :

```powershell
py -3.14 --version
```

**Résultat attendu :** `Python 3.14.x` (par exemple `Python 3.14.10`). Si Windows ne reconnaît pas `py -3.14`, terminer l'installation de Python 3.14 avant de continuer.

Une fois Python 3.14 installé, ouvrir **VS Code → Terminal → Nouveau terminal** (PowerShell) dans Windows et exécuter :

```powershell
cd "$HOME\Documents\Sae\Projet_SAE302"
py -3.14 --version
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si la commande `py -3.14 --version` échoue, utiliser `py --list` pour vérifier les versions installées, puis **installer Python 3.14** si nécessaire. Sur Windows, la commande de lancement utilise **`.venv\Scripts\python.exe`**, et **pas** `.venv-debian`. Sur Debian 13, utiliser la version Python 3 fournie par `apt` : il n'est pas demandé d'y installer Python 3.14.

Tests de la simulation locale :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe main.py
```

Dans `main.py`, vérifier les feux et le choix du scénario : c'est **le mode local**, sans réseau.

**Erreur fréquente :** si PowerShell affiche `C:\Users\toto\Documents\Sae>` au lieu de `...\Sae\Projet_SAE302>`, il faut d'abord taper `cd Projet_SAE302` avant de lancer un fichier du projet.

## 4. Préparer Debian 13

### 4.A. Autoriser l'utilisateur Debian à utiliser `sudo` (si nécessaire)

Sur certaines installations de Debian 13, l'utilisateur créé (ici **`toto`**) n'appartient pas au groupe `sudo`. Si une commande affiche **« toto n'est pas dans le fichier sudoers »**, corriger les droits avant de continuer. À faire uniquement sur une VM dont vous êtes administrateur.

**1. Passer en administrateur dans le terminal Debian :**

```bash
su -
```

Saisir le mot de passe **root** choisi à l'installation de Debian. L'invite devient `root@vbox:~#`.

**2. Ajouter l'utilisateur `toto` au groupe `sudo` :**

```bash
usermod -aG sudo toto
groups toto
```

La commande `groups toto` doit inclure **`sudo`**. Remplacer `toto` par le vrai nom d'utilisateur si celui-ci est différent. Il n'est pas nécessaire de modifier directement le fichier `/etc/sudoers` : le groupe `sudo` possède déjà les droits prévus sur une installation Debian classique.

**3. Appliquer les droits et vérifier :**

```bash
reboot
```

Après le redémarrage, se reconnecter **avec `toto`** (pas `root`), ouvrir un terminal puis saisir :

```bash
sudo whoami
```

Le résultat attendu est **`root`**. Les commandes `sudo apt ...`, `sudo systemctl ...` et `sudo mariadb` du reste du guide peuvent alors être utilisées normalement.

**Si `sudo` fonctionne déjà**, ne rien modifier et passer directement à l'étape suivante. Si vous n'avez pas le mot de passe root, demander à l'administrateur de la VM d'accorder les droits nécessaires.

### 4.B. Installer les logiciels sur Debian

Dans un terminal **en utilisateur normal `toto`**, exécuter :

**Attention au chemin après `su -` :** `~` désigne alors `/root`, pas `/home/toto`. Si vous devez travailler en root dans le projet, utiliser `cd /home/toto/Projet_SAE302` (et jamais `cd ~/Projet_SAE302`). Cette situation est également expliquée à l'étape 5.


```bash
whoami
ip -br a
sudo apt update
sudo apt install -y python3 python3-venv python3-pip mariadb-server openssh-server unzip
sudo systemctl enable --now mariadb ssh
sudo systemctl is-active mariadb
sudo systemctl is-active ssh
```

Résultat attendu des deux dernières commandes : `active`.

Depuis le dossier **`~/Projet_SAE302`** :

```bash
cd ~/Projet_SAE302
python3 -m venv .venv-debian
./.venv-debian/bin/python -m pip install PyMySQL==1.1.2
```

On n'installe pas nécessairement PySide6 sur Debian, car la fenêtre Qt est affichée sous Windows. **Les environnements virtuels Windows et Debian sont différents : ne jamais copier `.venv/` d'une VM sur l'autre.**

## 5. Préparer MariaDB sur Debian (première installation seulement)

Importer le script **existant de Huy-Ming** (`sql/01_schema.sql`). Choisir **une seule méthode**, selon les droits de l'utilisateur Debian :

**Méthode A — Si `sudo` fonctionne (utilisateur autorisé) :** depuis le terminal de `toto` :

```bash
cd ~/Projet_SAE302
sudo mariadb < sql/01_schema.sql
sudo mariadb
```

**Méthode B — Si Debian affiche « toto n'est pas dans le fichier sudoers » (comme dans notre VM) :** depuis le terminal de `toto`, passer en administrateur :

```bash
su -
# Entrer le mot de passe root
cd /home/toto/Projet_SAE302
mariadb < sql/01_schema.sql
mariadb
```

**Pourquoi utiliser `/home/toto/Projet_SAE302` et pas `~/Projet_SAE302` ?** Après `su -`, le `~` correspond à **`/root`**. La commande `cd ~/Projet_SAE302` cherche donc un dossier `/root/Projet_SAE302`, qui n'existe pas. Le chemin `/home/toto/Projet_SAE302` pointe vers le bon dossier du projet.

Résultat attendu : la commande d'importation ne signale pas d'erreur ; la commande `mariadb` ouvre l'invite SQL `MariaDB [(none)]>`. Dans cette invite SQL, taper :

```sql
USE sae302;
SHOW TABLES;
CREATE USER IF NOT EXISTS 'sae_youssef'@'127.0.0.1'
  IDENTIFIED BY 'REMPLACER_PAR_UN_MOT_DE_PASSE_PRIVE';
GRANT SELECT, INSERT, UPDATE ON sae302.* TO 'sae_youssef'@'127.0.0.1';
EXIT;
```

Les quatre tables attendues sont `scenarios`, `comparisons`, `trials`, `events`.

**Après `EXIT;` dans MariaDB :** si vous aviez utilisé la méthode B, vous êtes toujours dans le terminal `root@vbox:~#`. Tapez alors `exit` **une seconde fois** pour revenir à `toto@vbox:~/Projet_SAE302$` avant de créer `config.ini` ou de lancer Python :

```bash
exit
cd ~/Projet_SAE302
```

Le script `sql/01_schema.sql` utilise `CREATE ... IF NOT EXISTS` : il n'est pas prévu pour remplacer/migrer une ancienne structure différente. Si une base existe déjà, **ne pas supprimer ses tables** ; comparer d'abord le schéma.

**Sur une installation existante :** si l'utilisateur SQL existe déjà, `CREATE USER IF NOT EXISTS` **ne change pas** son mot de passe. Utiliser le mot de passe déjà configuré, ou demander à l'administrateur de le renouveler avec `ALTER USER`. Si un ancien mot de passe a été montré dans une capture ou partagé, le renouveler avant publication.

### Étape obligatoire — Renseigner les identifiants MariaDB dans `config.ini` AVANT de lancer les scénarios

**Le fichier `config.example.ini` contient un utilisateur d'exemple (`sae_huyming`) qui ne correspond pas forcément au compte créé à l'étape précédente.** Si l'on conserve ce nom ou le mot de passe fictif, Python affichera une erreur `Access denied for user` et les comparaisons ne pourront pas être enregistrées.

En étant connecté sur Debian avec l'utilisateur normal (`toto` dans cet exemple), exécuter :

```bash
cd ~/Projet_SAE302
cp config.example.ini config.ini
nano config.ini
```

Dans la section `[database]`, **remplacer obligatoirement** :

- `user` par **le nom exact du compte MariaDB créé plus haut** avec `CREATE USER` (par exemple `sae_youssef`, et non `sae_huyming` si ce compte n'a pas été créé) ;
- `password` par **le même mot de passe que celui choisi lors de la commande `CREATE USER`** ;
- conserver `host = 127.0.0.1`, `port = 3306` et `database = sae302` pour l'installation locale décrite ici.

Exemple **uniquement si le compte créé précédemment s'appelle `sae_youssef`** :

```ini
[database]
host = 127.0.0.1
port = 3306
database = sae302
user = sae_youssef
password = MOT_DE_PASSE_CHOISI_LORS_DU_CREATE_USER
ssl_ca =
```

**Ne pas laisser** `MOT_DE_PASSE_CHOISI_LORS_DU_CREATE_USER` tel quel : saisir le vrai mot de passe choisi par l'étudiant, et ne pas le montrer dans les captures d'écran. Avec Nano, enregistrer avec **Ctrl + O**, **Entrée**, puis quitter avec **Ctrl + X**.

**Faire ce réglage avant l'étape 6 (`executer_scenarios.py`) et avant de lancer `serveur_central.py`**, car ces deux programmes utilisent `config.ini` pour accéder à MariaDB.

Puis :

```bash
chmod 600 config.ini
mariadb -h 127.0.0.1 -u sae_youssef -p sae302
```

Saisir **le même mot de passe que dans `config.ini`** et exécuter `SHOW TABLES;`, puis `EXIT;`. Si l'étudiant a choisi un autre nom d'utilisateur que `sae_youssef`, il faut également remplacer ce nom dans la commande de test ci-dessus.

**Ne jamais publier `config.ini` sur GitHub.** Seul `config.example.ini`, avec ses valeurs fictives, doit être partagé.

## 6. Vérifier la partie SQL de Huy-Ming sans réseau

Toujours **sur Debian** :

```bash
cd ~/Projet_SAE302
./.venv-debian/bin/python executer_scenarios.py --scenario S01 --config config.ini
```

Cette commande exécute **le moteur en local** et sauvegarde la comparaison dans MariaDB. Elle ne valide pas les messages TCP de Youssef. On peut ensuite remplacer `S01` par `tous` pour les trois scénarios.

## 7. Lancer le serveur de Youssef sur Debian

Dans son terminal dédié :

```bash
cd ~/Projet_SAE302
./.venv-debian/bin/python serveur_central.py --host 0.0.0.0 --port 5000 --config config.ini
```

Attendre un message du type :

```text
INFO Serveur Youssef démarré sur 0.0.0.0:5000 (modèle virtuel seulement)
```

**Laisser ce terminal ouvert.** Le serveur écoute le port TCP `5000` de Debian. La version simplifiée traite **une connexion à la fois** ; ne pas lancer deux comparaisons simultanément. Ne pas exposer ce port sur Internet : il n'y a pas d'authentification réseau pour cette maquette.

## 8. Vérifier la communication Windows -> Debian

**Avant de lancer une commande TCP sur Windows, relever l'adresse IPv4 Host-only de Debian** :

```bash
# Sur la VM Debian 13
ip -br a
```

Repérer la ligne de la carte **Réseau privé hôte / Host-only**, par exemple `enp0s3  UP  192.168.56.109/24`. Dans cet exemple, l'adresse du serveur à utiliser sur Windows est **`192.168.56.109`**. **L'adresse ci-dessous est un exemple de présentation : remplacer `192.168.56.109` par l'adresse réellement affichée sur votre Debian.** Ne pas utiliser l'adresse inscrite dans `config.ini` : `127.0.0.1` correspond à MariaDB sur Debian, pas à l'adresse du serveur TCP vu depuis Windows.

**Sous Windows 11** :

```powershell
Test-NetConnection 192.168.56.109 -Port 5000
```

Résultat attendu : `TcpTestSucceeded : True`.

Si c'est `False`, vérifier l'IP Host-only de Debian, le serveur démarré, le port et les paramètres réseau des deux VM.

Toujours sous Windows, dans `Projet_SAE302` :

```powershell
.\.venv\Scripts\python.exe client_reseau.py --host 192.168.56.109 --scenario tous
```

Cette commande lance **trois comparaisons** S01, S02, S03, avec **deux essais par comparaison** : SANS puis AVEC. Le client envoie les états du carrefour et applique les ordres du serveur Debian. Les résultats sont relus dans MariaDB avant affichage.

Résultats observés pendant les essais de référence de cette configuration :

| Scénario | Sans priorité | Avec priorité | Gain simulé |
| --- | ---: | ---: | ---: |
| S01 | 20,60 s | 13,40 s | 7,20 s |
| S02 | 23,60 s | 14,00 s | 9,60 s |
| S03 | 24,95 s | 17,75 s | 7,20 s |

Ce sont des **mesures simulées de référence**, pas une garantie pour toute version modifiée du moteur ou tout autre scénario.

## 9. Lancer l'interface graphique en mode réseau

Sur **Windows 11**, dans un autre terminal PowerShell du dossier `Projet_SAE302` :

```powershell
.\.venv\Scripts\python.exe interface_reseau.py --host 192.168.56.109
```

Dans la fenêtre :

1. Choisir **S01 — Ambulance seule**.
2. Cliquer sur **Comparer via serveur TCP** (le bouton **Démarrer réseau** lance la même comparaison).
3. Observer les deux essais **SANS puis AVEC** et les changements des feux décidés par Debian.
4. Lire les deux durées et le gain. Recommencer avec S02 et S03.
5. Le bouton **Arrêter essai** demande une interruption. Une fenêtre d'avertissement peut apparaître : dans l'implémentation actuelle, l'interruption remonte comme une exception du travail réseau.

Le temps affiché pendant l'animation est le **temps courant simulé**. La durée d'un essai est calculée entre le départ effectif et l'arrivée de l'ambulance, ce qui explique que les deux affichages ne soient pas toujours identiques.

## 10. Vérifier les lignes enregistrées dans MariaDB

Sur **Debian**, ouvrir un **deuxième** terminal (ne pas arrêter le serveur). Si `sudo` fonctionne, entrer dans MariaDB avec `sudo mariadb` ; sinon, passer en `root` avec `su -` puis taper `mariadb` :

```bash
# Avec sudo :
sudo mariadb
# Ou, si « toto n'est pas dans le fichier sudoers » :
su -
mariadb
```

```sql
USE sae302;
SELECT c.scenario_id, c.data_origin, c.created_at,
       t.mode, t.status, t.duration_s, t.interruption_reason
FROM trials AS t
JOIN comparisons AS c ON t.comparison_id = c.comparison_id
ORDER BY c.created_at DESC, t.mode
LIMIT 12;
```

Les essais terminés ont normalement `status = 'TERMINE'` et une durée numérique. Un essai arrêté peut avoir `status = 'INTERROMPU'` avec `duration_s = NULL` : ce n'est pas une comparaison achevée.

> Ne pas trier par `id` : la table `trials` possède la clé `trial_id`, pas de colonne `id`. Pour lire toutes les comparaisons, utiliser également `sql/02_lire_resultats.sql`.



## 11. Comment le protocole fonctionne

Le client ouvre une connexion TCP vers Debian et envoie **un objet JSON par ligne** (chaque ligne se termine par `\n`). Le protocole de données de Huy-Ming vérifie notamment les identifiants et les champs des événements.

| Client Windows -> Debian | Réponse de Debian |
| --- | --- |
| `create_comparison` + scénario | `comparison_ready` + identifiants |
| `choose_trial` + mode SANS/AVEC | `start_trial` |
| `trial_started`, `priority_departed`, `priority_arrived` | `ack` après traitement SQL |
| `traffic_state` + heure simulée + état des feux + zone libre | `ok` ou `feu_commande` |
| `priority_request` / `priority_clear` en mode AVEC | `feu_commande` |
| `get_results` | `comparison_result` + durées/gain |

La stratégie `priorite_simple.py` suit les états `NORMAL`, `ORANGE`, `ROUGE`, `PRIORITE`, `RETOUR_ORANGE`, `RETOUR_ROUGE` avant de revenir à `NORMAL`. Les durées d'orange et tous rouges viennent du scénario ; la vérification de zone libre est une **approximation géométrique**, pas une preuve d'absence de conflit réel.

## 12. Vérifier que le dossier téléchargé est complet

Après la décompression du ZIP sur chaque VM, le dossier `Projet_SAE302` doit contenir **les fichiers du projet**, en particulier :

- **Kerem :** `main.py`, `simulation.py`, `test_simulation.py`.
- **Huy-Ming :** `scenarios/`, `scenarios_loader.py`, `sae_data/`, `sql/`, `executer_scenarios.py`, `tests_data/`.
- **Youssef :** `serveur_central.py`, `priorite_simple.py`, `client_reseau.py`, `interface_reseau.py`, `test_erreurs_tcp.py`.
- **Installation et aide :** `requirements.txt`, `config.example.ini`, `README.md`, `GUIDE_YOUSSEF.md`.

Les fichiers **`.venv/` et `.venv-debian/` ne sont pas fournis** : ils sont créés respectivement aux étapes 3 et 4. Le fichier **`config.ini`** est privé et doit être créé sur Debian à l'étape 5. **Ne pas supprimer ou écraser la base MariaDB** d'une installation existante.

Pour remettre ce projet à un autre étudiant, lui fournir **le même ZIP** et lui demander de suivre le guide à partir de l'étape 1. **Aucune commande `git clone` n'est nécessaire pour installer ou lancer la SAÉ.**

## 13. Problèmes courants

| Message | Vérification |
| --- | --- |
| `CommandNotFoundException` sur `.venv\Scripts\python.exe` | Être dans `Projet_SAE302`, pas seulement dans `Sae` |
| `No module named PySide6` | Sur Windows, relancer `pip install -r requirements.txt` dans `.venv` |
| `ModuleNotFoundError: priorite_simple` | Copier `priorite_simple.py` dans **le même dossier** que `serveur_central.py` sur Debian |
| `Connection refused` | Serveur arrêté, mauvaise IP/port ou panne réseau |
| `Address already in use` | Une autre instance utilise le port 5000 ; arrêter l'ancien processus |
| `Access denied for user` | Avant de lancer les scénarios, ouvrir `nano config.ini` et remplacer `user` et `password` par les identifiants **créés précédemment dans MariaDB** ; ne pas garder l'utilisateur d'exemple `sae_huyming` si le compte réel est `sae_youssef` |
| `Table ... doesn't exist` | Vérifier `SHOW TABLES;` et l'import du bon schéma SQL |
| `Unknown column 'id'` | Utiliser `trial_id` / `comparison_id` ; consulter `DESCRIBE trials;` |
| Erreur `scp` | Vérifier `ssh` actif sur Debian (`systemctl is-active ssh`), l'IP Host-only et le port 22 (`Test-NetConnection IP_DEBIAN -Port 22`) |
| Debian ne peut pas installer avec `apt` / `pip` : « échec temporaire dans la résolution du nom » | Vérifier la configuration DHCP de la carte NAT dans `/etc/network/interfaces` (étape 1.B), `ip route`, puis `getent ahostsv4 deb.debian.org` ; vérifier également le gestionnaire réseau actif et le DNS |
| `toto n'est pas dans le fichier sudoers` | Suivre l'étape 4.A : `su -`, `usermod -aG sudo toto`, `reboot`, puis vérifier `sudo whoami` |
| Debian ne peut pas ping Windows | Ajouter la règle ICMPv4 entrante sur Windows (étape 1.D) et vérifier les adresses IP Host-only actuelles |
| La fenêtre Qt se fige / l'essai échoue | Lire les messages Windows et le journal Debian, vérifier que le serveur répond avant de relancer |



**Limites :** une connexion à la fois côté Debian ; machine à états pédagogique ; Qt testé en usage réel sur l'ancienne structure avant la simplification, à revérifier sur la nouvelle ; aucune validation sur un équipement routier réel.
