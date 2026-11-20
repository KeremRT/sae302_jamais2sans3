import configparser
import os
from pathlib import Path


# On garde au même endroit les réglages pour se connecter à MariaDB.
class ConnexionMariaDB:

    # On lit le fichier de réglages et on récupère le mot de passe.
    def __init__(self, config_path='config.ini'):
        config = configparser.ConfigParser(interpolation=None)
        fichiers_lus = config.read(Path(config_path), encoding='utf-8')
        if not fichiers_lus:
            raise ValueError('Configuration absente : copier config.example.ini vers config.ini.')

        db = config['database']
        self.__host = db.get('host', '127.0.0.1')
        self.__port = db.getint('port', 3306)
        self.__user = db['user']
        self.__database = db.get('database', 'sae302')
        self.__ca = db.get('ssl_ca', '').strip()

        # On prend le mot de passe de l’environnement en priorité.
        if 'SAE_DB_PASSWORD' in os.environ:
            self.__password = os.environ['SAE_DB_PASSWORD']
        else:
            self.__password = db.get('password', '')
        if not self.__password or self.__password == 'A_REMPLACER':
            raise ValueError('Renseigner le mot de passe dans config.ini ou SAE_DB_PASSWORD.')

    # On ouvre une connexion avec les réglages déjà lus.
    def connecter(self):
        import pymysql

        # Si un certificat est fourni, on vérifie le certificat et l’identité du serveur.
        if self.__ca:
            return pymysql.connect(
                host=self.__host,
                port=self.__port,
                user=self.__user,
                password=self.__password,
                database=self.__database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=5,
                read_timeout=10,
                write_timeout=10,
                ssl_ca=self.__ca,
                ssl_verify_cert=True,
                ssl_verify_identity=True,
            )

        return pymysql.connect(
            host=self.__host,
            port=self.__port,
            user=self.__user,
            password=self.__password,
            database=self.__database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
        )


# On renvoie la méthode que le programme pourra appeler pour ouvrir une connexion.
def creer_factory(config_path='config.ini'):
    configuration = ConnexionMariaDB(config_path)
    return configuration.connecter
