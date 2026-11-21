import configparser


# On garde au même endroit les réglages pour se connecter à MariaDB.
class ConnexionMariaDB:

    # On lit le fichier de réglages et on récupère le mot de passe.
    def __init__(self, config_path='config.ini'):
        # On lit les valeurs telles qu'elles sont écrites, même si le mot de passe contient un %.
        config = configparser.ConfigParser(interpolation=None)
        if not config.read(config_path, encoding='utf-8'):
            raise ValueError('Configuration absente : copier config.example.ini vers config.ini.')

        db = config['database']
        self.__host = db.get('host', '127.0.0.1')
        self.__port = db.getint('port', 3306)
        self.__user = db['user']
        self.__database = db.get('database', 'sae302')

        # On lit le mot de passe dans le fichier INI privé.
        self.__password = db.get('password', '')
        if not self.__password or self.__password == 'A_REMPLACER':
            raise ValueError('Renseigner le mot de passe dans le fichier INI utilisé.')

    # On ouvre une connexion avec les réglages déjà lus.
    def connecter(self):
        import pymysql

        # DictCursor permet de lire une colonne par son nom, par exemple essai['status'].
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
