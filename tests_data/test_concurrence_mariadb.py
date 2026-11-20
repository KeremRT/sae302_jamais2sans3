"""Tests concurrents sur une base MariaDB dédiée, sans suppression de données."""

from concurrent.futures import ThreadPoolExecutor
import copy
from decimal import Decimal
import json
import os
from pathlib import Path
from threading import Barrier
import unittest
from uuid import uuid4

from demo import generer_evenement
from sae_data import MesuresRepository, DonneesInvalides
from sae_data.connexion import creer_factory


@unittest.skipUnless(os.environ.get('SAE_TEST_CONFIG'), 'Base MariaDB de test requise')
class ConcurrenceMariaDBTests(unittest.TestCase):
    """Vérifie la déduplication et l'isolation de plusieurs connexions réelles."""

    def setUp(self):
        """Crée une comparaison EXEMPLE propre à chaque test."""
        self.factory = creer_factory(os.environ['SAE_TEST_CONFIG'])
        with self.factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT VERSION() AS version, DATABASE() AS db')
                server = cursor.fetchone()
                self.assertIn('MariaDB', server['version'])
                self.assertNotEqual(server['db'], 'sae302', 'Utiliser une base de test séparée')
        self.repo = MesuresRepository(self.factory)
        self.cid = str(uuid4())
        config = json.loads((Path(__file__).resolve().parents[1] / 'scenarios/S02.json').read_text(encoding='utf-8'))
        self.repo.creer_comparaison(config, self.cid, 'EXEMPLE')
        self.trials = {mode: self.repo.ouvrir_essai(self.cid, mode, str(uuid4()))
                       for mode in ('SANS', 'AVEC')}

    def run_parallel(self, jobs):
        """Lance les appels après une barrière et propage leurs erreurs."""
        barrier = Barrier(len(jobs))

        def worker(job):
            """Attend les autres workers avant l'appel au module."""
            barrier.wait(timeout=15)
            return job()

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [pool.submit(worker, job) for job in jobs]
            return [future.result(timeout=30) for future in futures]

    def count_events(self, trial_id):
        """Relit le nombre d'événements avec une connexion indépendante."""
        with self.factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS n FROM events WHERE trial_id=%s', (trial_id,))
                return cursor.fetchone()['n']

    def test_huit_retransmissions_identiques(self):
        """Huit connexions ne doivent enregistrer qu'un événement."""
        trial = self.trials['SANS']
        event = generer_evenement(trial, 'trial_started', 0)
        results = self.run_parallel([lambda: self.repo.traiter_evenement(copy.deepcopy(event))
                                     for _ in range(8)])
        self.assertEqual(sum(not result['duplicate'] for result in results), 1)
        self.assertEqual(self.count_events(trial['trial_id']), 1)

    def test_meme_identifiant_contenus_differents(self):
        """Une seule version concurrente est acceptée, l'autre est rejetée."""
        trial = self.trials['SANS']
        self.repo.traiter_evenement(generer_evenement(trial, 'trial_started', 0))
        first = generer_evenement(trial, 'priority_departed', 25)
        second = dict(first, sim_time_s=26)

        def attempt(event):
            """Distingue un rejet métier attendu d'une panne SQL inattendue."""
            try:
                self.repo.traiter_evenement(event)
                return 'accepted'
            except DonneesInvalides:
                return 'rejected'

        results = self.run_parallel([lambda: attempt(first), lambda: attempt(second)])
        self.assertCountEqual(results, ['accepted', 'rejected'])
        self.assertEqual(self.count_events(trial['trial_id']), 2)
        saved = self.repo.lire_comparaison(self.cid)['essais']['SANS']
        self.assertIn(saved['departure_s'], (Decimal('25'), Decimal('26')))

    def test_deux_essais_en_parallele(self):
        """Les deux essais restent distincts et leur gain est correctement relu."""
        def finish(mode, arrival):
            """Envoie la séquence ordonnée d'un essai depuis un worker."""
            trial = self.trials[mode]
            for kind, instant in [('trial_started', 0), ('priority_departed', 25),
                                  ('priority_arrived', arrival)]:
                self.repo.traiter_evenement(generer_evenement(trial, kind, instant))

        self.run_parallel([lambda: finish('SANS', 52.4), lambda: finish('AVEC', 47)])
        result = self.repo.lire_comparaison(self.cid)
        self.assertEqual(result['gain_s'], Decimal('5.4'))
        for mode in ('SANS', 'AVEC'):
            self.assertEqual(result['essais'][mode]['status'], 'TERMINE')
            self.assertEqual(self.count_events(self.trials[mode]['trial_id']), 3)
