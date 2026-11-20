"""Tests de bout en bout TCP avec SQLite de test. MariaDB reste à valider sur la VM."""
import tempfile
import threading
import unittest
from pathlib import Path

from client_reseau import executer_comparaison_reseau
from sae_data import MesuresRepository
from serveur_central import Gestionnaire, Serveur
from tests_data.support import SQLiteConnection, installer_schema_sqlite


class TestServeurYoussef(unittest.TestCase):
    """Teste les comparaisons complètes via TCP avec une base SQLite temporaire."""
    def setUp(self):
        """Prépare une base temporaire et un serveur TCP pour chaque test."""
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / 'tests.sqlite'
        schema = Path(__file__).resolve().parents[1] / 'sql' / '01_schema.sql'
        installer_schema_sqlite(schema.read_text(encoding='utf8'), path)
        self.server = Serveur(('127.0.0.1', 0), Gestionnaire)
        self.server.repo = MesuresRepository(lambda: SQLiteConnection(path))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        """Arrête le serveur de test et libère les fichiers temporaires."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def test_s01(self):
        """Vérifie la comparaison réseau du scénario S01 et la commande de priorité."""
        result = executer_comparaison_reseau('S01','127.0.0.1',self.port)
        self.assertEqual(result['SANS']['status'],'TERMINE')
        self.assertEqual(result['AVEC']['status'],'TERMINE')
        self.assertGreater(result['gain_s'],0)
        self.assertIn('EO_GREEN',[c[2] for c in result['commandes_feux']])

    def test_s02(self):
        """Vérifie la comparaison réseau du scénario S02 et la transition tous rouges."""
        result = executer_comparaison_reseau('S02','127.0.0.1',self.port)
        self.assertEqual(result['AVEC']['status'],'TERMINE')
        self.assertIn('ALL_RED',[c[2] for c in result['commandes_feux']])
        self.assertGreater(result['gain_s'],0)

    def test_s03(self):
        """Vérifie la comparaison réseau du scénario S03."""
        result = executer_comparaison_reseau('S03','127.0.0.1',self.port)
        self.assertEqual(result['AVEC']['status'],'TERMINE')
        self.assertGreater(result['gain_s'],0)

if __name__ == '__main__':
    unittest.main()
