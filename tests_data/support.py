"""Adaptateur de tests SQLite uniquement, PAS un remplacement de MariaDB.

Le schema SQL livre est adapte pour les tests locaux : ENUM devient TEXT,
FOR UPDATE est retire, et les marqueurs %s deviennent ?. Les verrous MariaDB,
les droits SQL et les particularites serveur ne sont donc pas valides ici.
Definir SAE_TEST_CONFIG pour executer les memes tests avec une vraie MariaDB.
"""

from decimal import Decimal
import re
import sqlite3


class SQLiteCursor:
    """Adapte un curseur SQLite aux requêtes utilisées dans les tests du dépôt."""
    def __init__(self, cur):
        """Mémorise le curseur SQLite utilisé par les tests."""
        self.cur = cur

    def execute(self, sql, params=()):
        """Adapte la requête et l’exécute sur SQLite."""
        sql = sql.replace('%s', '?').replace(' FOR UPDATE', '')
        self.cur.execute(sql, tuple(str(x) if isinstance(x, Decimal) else x for x in params))

    @staticmethod
    def _row(row):
        """Transforme une ligne SQLite en dictionnaire compatible avec le dépôt."""
        if row is None:
            return None
        result = dict(row)
        for key in ('departure_s', 'arrival_s', 'duration_s', 'last_sim_time_s'):
            if key in result and result[key] is not None:
                result[key] = Decimal(str(result[key]))
        return result

    def fetchone(self):
        """Renvoie une seule ligne de résultat sous forme de dictionnaire."""
        return self._row(self.cur.fetchone())

    def fetchall(self):
        """Renvoie toutes les lignes de résultat sous forme de dictionnaires."""
        return [self._row(r) for r in self.cur.fetchall()]

    def close(self):
        """Ferme le curseur SQLite."""
        self.cur.close()


class SQLiteConnection:
    """Fournit une connexion SQLite compatible avec les tests du stockage."""
    def __init__(self, path):
        """Ouvre une connexion SQLite pour les tests du dépôt."""
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')

    def begin(self):
        """Démarre une transaction de test."""
        self.conn.execute('BEGIN')

    def cursor(self):
        """Renvoie un curseur adapté aux requêtes du dépôt."""
        return SQLiteCursor(self.conn.cursor())

    def commit(self):
        """Valide les écritures de la transaction."""
        self.conn.commit()

    def rollback(self):
        """Annule les écritures de la transaction en cours."""
        self.conn.rollback()

    def close(self):
        """Ferme la connexion SQLite."""
        self.conn.close()


def installer_schema_sqlite(sql, path):
    """Installe une version du schéma compatible avec SQLite pour les tests."""
    sql = re.sub(r'CREATE DATABASE IF NOT EXISTS sae302\s+CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;', '', sql)
    sql = sql.replace('USE sae302;', '')
    sql = sql.replace(' CHARACTER SET ascii COLLATE ascii_bin', '')
    sql = re.sub(r"ENUM\([^)]*\)", 'TEXT', sql)
    sql = sql.replace(' ENGINE=InnoDB', '').replace('CURRENT_TIMESTAMP(6)', 'CURRENT_TIMESTAMP')
    # SQLite emploie des flottants pour DECIMAL ; comparer a la microseconde.
    # MariaDB garde la contrainte exacte et son vrai type DECIMAL(18,6).
    sql = sql.replace('duration_s = arrival_s - departure_s',
                      'ROUND(duration_s * 1000000) = ROUND((arrival_s - departure_s) * 1000000)')
    sql = re.sub(r'\s*INDEX events_by_trial \(trial_id, sim_time_s\),', '', sql)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(sql)
    finally:
        conn.close()


class FailingCursor:
    """Simule une panne pendant une écriture pour vérifier le rollback."""
    def __init__(self, cursor):
        """Mémorise le curseur à envelopper pour simuler une panne."""
        self.cursor = cursor

    def execute(self, sql, params=()):
        """Simule une erreur pendant une écriture de test."""
        if sql.startswith('UPDATE trials SET'):
            raise RuntimeError('Echec SQL injecte APRES INSERT de l evenement.')
        return self.cursor.execute(sql, params)

    def __getattr__(self, name):
        """Transmet les attributs non redéfinis à l’objet encapsulé."""
        return getattr(self.cursor, name)


class FailingConnection:
    """Fournit un curseur qui simule une panne de stockage."""
    def __init__(self, conn):
        """Mémorise la connexion à envelopper pour simuler une panne."""
        self.conn = conn

    def cursor(self):
        """Renvoie un curseur simulant une panne."""
        return FailingCursor(self.conn.cursor())

    def __getattr__(self, name):
        """Transmet les attributs non redéfinis à l’objet encapsulé."""
        return getattr(self.conn, name)
