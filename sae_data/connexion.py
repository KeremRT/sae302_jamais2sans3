"""Une nouvelle connexion par operation : ne pas partager un curseur entre threads."""

import configparser
import os
from pathlib import Path


def creer_factory(config_path='config.ini'):
    """Le mot de passe peut aussi etre fourni via SAE_DB_PASSWORD."""
    import pymysql

    config = configparser.ConfigParser(interpolation=None)
    if not config.read(Path(config_path), encoding='utf-8'):
        raise ValueError('Configuration absente : copier config.example.ini vers config.ini.')
    db = config['database']
    password = os.environ.get('SAE_DB_PASSWORD', db.get('password', ''))
    if not password or password == 'A_REMPLACER':
        raise ValueError('Renseigner le mot de passe dans config.ini ou SAE_DB_PASSWORD.')
    params = dict(host=db.get('host', '127.0.0.1'), port=db.getint('port', 3306),
                  user=db['user'], password=password, database=db.get('database', 'sae302'),
                  charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor,
                  autocommit=False, connect_timeout=5, read_timeout=10, write_timeout=10)
    ca = db.get('ssl_ca', '').strip()
    if ca:
        params.update(ssl_ca=ca, ssl_verify_cert=True, ssl_verify_identity=True)

    def connecter():
        """Ouvre une nouvelle connexion MariaDB avec les paramètres configurés."""
        return pymysql.connect(**params)
    return connecter
