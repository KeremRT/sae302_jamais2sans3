import copy
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from sae_data import MesuresRepository, DonneesInvalides, ErreurStockage
from sae_data.connexion import creer_factory
from demo import generer_evenement
from support import SQLiteConnection, installer_schema_sqlite, FailingConnection

ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = None
        if os.environ.get('SAE_TEST_CONFIG'):
            self.factory = creer_factory(os.environ['SAE_TEST_CONFIG'])
        else:
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            path = Path(self.temp.name) / 'tests.sqlite'
            installer_schema_sqlite((ROOT/'sql/01_schema.sql').read_text(), path)
            self.factory = lambda: SQLiteConnection(path)
        self.repo = MesuresRepository(self.factory)
        self.config = json.loads((ROOT/'scenarios_v1/S02.json').read_text())
        self.cid = str(uuid4())
        self.repo.creer_comparaison(self.config, self.cid, 'EXEMPLE')
        self.sans = self.repo.ouvrir_essai(self.cid, 'SANS', str(uuid4()))
        self.avec = self.repo.ouvrir_essai(self.cid, 'AVEC', str(uuid4()))

    def send(self, trial, kind, t, **fields):
        event = generer_evenement(trial, kind, t)
        event.update(fields)
        return self.repo.traiter_evenement(event)

    def finish(self, trial, arrival):
        self.send(trial, 'trial_started', 0)
        self.send(trial, 'priority_departed', 25)
        self.send(trial, 'priority_arrived', arrival)

    def count_events(self, event_id):
        conn = self.factory()
        try:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) AS n FROM events WHERE event_id=%s', (event_id,))
            return cur.fetchone()['n']
        finally:
            conn.close()

    def test_gain_et_relecture(self):
        self.finish(self.sans, 52.4)
        self.finish(self.avec, 47)
        result = MesuresRepository(self.factory).lire_comparaison(self.cid)
        self.assertTrue(result['comparable'])
        self.assertEqual(result['gain_s'], Decimal('5.4'))
        self.assertEqual(result['data_origin'], 'EXEMPLE')

    def test_gain_negatif_conserve(self):
        self.finish(self.sans, 47)
        self.finish(self.avec, 52.4)
        self.assertEqual(self.repo.lire_comparaison(self.cid)['gain_s'], Decimal('-5.4'))

    def test_gain_nul(self):
        self.finish(self.sans, 47)
        self.finish(self.avec, 47)
        self.assertEqual(self.repo.lire_comparaison(self.cid)['gain_s'], Decimal('0'))

    def test_comparaison_incomplete(self):
        self.finish(self.sans, 52.4)
        result = self.repo.lire_comparaison(self.cid)
        self.assertFalse(result['comparable'])
        self.assertIsNone(result['gain_s'])

    def test_interruption_avant_depart(self):
        self.send(self.sans, 'trial_started', 0)
        self.send(self.sans, 'trial_interrupted', 7, reason='user_stop')
        trial = self.repo.lire_comparaison(self.cid)['essais']['SANS']
        self.assertEqual(trial['status'], 'INTERROMPU')
        self.assertIsNone(trial['duration_s'])

    def test_interruption_avant_lancement(self):
        self.send(self.sans, 'trial_interrupted', 0, reason='connection_lost')
        self.assertEqual(self.repo.lire_comparaison(self.cid)['essais']['SANS']['status'], 'INTERROMPU')

    def test_timeout(self):
        self.send(self.sans, 'trial_started', 0)
        self.send(self.sans, 'priority_departed', 25)
        self.send(self.sans, 'trial_interrupted', 120, reason='timeout')
        self.finish(self.avec, 47)
        self.assertIsNone(self.repo.lire_comparaison(self.cid)['gain_s'])

    def test_doublon_apres_fin(self):
        event = generer_evenement(self.sans, 'trial_started', 0)
        self.repo.traiter_evenement(event)
        self.send(self.sans, 'priority_departed', 25)
        self.send(self.sans, 'priority_arrived', 52.4)
        self.assertTrue(self.repo.traiter_evenement(event)['duplicate'])
        self.assertEqual(self.count_events(event['event_id']), 1)

    def test_doublon_different(self):
        self.send(self.sans, 'trial_started', 0)
        event = generer_evenement(self.sans, 'priority_departed', 25)
        self.repo.traiter_evenement(event)
        event['sim_time_s'] = 26
        with self.assertRaises(DonneesInvalides):
            self.repo.traiter_evenement(event)

    def test_mauvais_mode(self):
        with self.assertRaises(DonneesInvalides):
            self.send(self.sans, 'trial_started', 0, mode='AVEC')

    def test_essai_inconnu(self):
        with self.assertRaises(DonneesInvalides):
            self.send(self.sans, 'trial_started', 0, trial_id=str(uuid4()))

    def test_mauvaise_comparaison(self):
        with self.assertRaises(DonneesInvalides):
            self.send(self.sans, 'trial_started', 0, comparison_id=str(uuid4()))

    def test_arrivee_sans_depart(self):
        self.send(self.sans, 'trial_started', 0)
        with self.assertRaises(DonneesInvalides):
            self.send(self.sans, 'priority_arrived', 30)

    def test_temps_recule(self):
        self.send(self.sans, 'trial_started', 0)
        self.send(self.sans, 'priority_departed', 25)
        with self.assertRaises(DonneesInvalides):
            self.send(self.sans, 'priority_arrived', 24)

    def test_evenement_apres_interruption(self):
        self.send(self.sans, 'trial_interrupted', 0, reason='connection_lost')
        with self.assertRaises(DonneesInvalides):
            self.send(self.sans, 'trial_started', 0)

    def test_temps_invalides(self):
        for bad in [True, -1, 121, '25', float('nan'), float('inf'), 0.0000001]:
            with self.subTest(bad=bad), self.assertRaises(DonneesInvalides):
                self.send(self.sans, 'priority_departed', bad)

    def test_precision_sans_arrondi(self):
        self.send(self.sans, 'trial_started', 0)
        self.send(self.sans, 'priority_departed', 25.000001)
        self.send(self.sans, 'priority_arrived', 25.000003)
        t = self.repo.lire_comparaison(self.cid)['essais']['SANS']
        self.assertEqual(t['duration_s'], Decimal('0.000002'))

    def test_version_et_champs_invalides(self):
        for fields in [{'protocol_version': True}, {'scenario_version': True},
                       {'reason': 'timeout'}, {'autre': 1}, {'vehicle_id': 'A2'}]:
            with self.subTest(fields=fields), self.assertRaises(DonneesInvalides):
                self.send(self.sans, 'priority_departed', 25, **fields)

    def test_scenario_modifie_meme_version(self):
        config = copy.deepcopy(self.config)
        config['vehicles']['free_speed_m_s'] = 11
        with self.assertRaises(DonneesInvalides):
            self.repo.creer_comparaison(config, str(uuid4()), 'EXEMPLE')

    def test_une_seule_paire_par_comparaison(self):
        with self.assertRaises(DonneesInvalides):
            self.repo.ouvrir_essai(self.cid, 'SANS', str(uuid4()))

    def test_creation_idempotente(self):
        self.repo.creer_comparaison(self.config, self.cid, 'EXEMPLE')
        self.repo.ouvrir_essai(self.cid, 'SANS', self.sans['trial_id'])

    def test_rollback_apres_insertion_evenement(self):
        event = generer_evenement(self.sans, 'trial_started', 0)
        failing = MesuresRepository(lambda: FailingConnection(self.factory()))
        with self.assertRaises(ErreurStockage):
            failing.traiter_evenement(event)
        self.assertEqual(self.count_events(event['event_id']), 0)
        self.assertEqual(self.repo.lire_comparaison(self.cid)['essais']['SANS']['status'], 'PRET')
        # Le meme evenement peut etre rejoue apres correction, sans doublon.
        self.repo.traiter_evenement(event)
        self.assertEqual(self.count_events(event['event_id']), 1)

    def test_panne_connexion(self):
        def fail():
            raise ConnectionError('Panne injectee.')
        with self.assertRaises(ErreurStockage):
            MesuresRepository(fail).lire_comparaison(self.cid)
