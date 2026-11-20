"""Vérifications des scénarios et du raccordement au contrat de données."""
import copy
import unittest
from uuid import uuid4

from executer_scenarios import executer_comparaison, executer_essai
from scenarios_loader import charger_scenario, calendrier
from sae_data.validation import valider_evenement
from simulation import Simulation, TRAJETS, comparer


class TestScenarios(unittest.TestCase):
    """Teste les mesures, la reproductibilité et les cas concrets des fiches."""

    def test_trois_scenarios_reproductibles(self):
        """Chaque paire termine et conserve sa configuration d'entrée."""
        for sid in ('S01', 'S02', 'S03'):
            with self.subTest(scenario=sid):
                config = charger_scenario(sid)
                original = copy.deepcopy(config)
                first = executer_comparaison(config)
                second = executer_comparaison(config)
                self.assertEqual(config, original)
                self.assertEqual(first['gain_s'], second['gain_s'])
                self.assertNotEqual(first['comparison_id'], second['comparison_id'])
                self.assertEqual(len({t['trial_id'] for t in first['trials']}), 2)
                for a, b in zip(first['trials'], second['trials']):
                    self.assertEqual(a['status'], 'TERMINE')
                    self.assertEqual(a['duration_s'], b['duration_s'])
                    self.assertEqual(a['entries'], b['entries'])
                    for event in a['events']:
                        valider_evenement(event)
                    start, departure, arrival = a['events']
                    self.assertEqual(start['sim_time_s'], 0)
                    self.assertAlmostEqual(a['duration_s'], arrival['sim_time_s']-departure['sim_time_s'])
                sans, avec, gain = comparer(config)
                self.assertEqual(sans, first['trials'][0]['duration_s'])
                self.assertEqual(avec, first['trials'][1]['duration_s'])
                self.assertAlmostEqual(gain, first['gain_s'])

    def test_entree_occupee_ne_perd_pas_de_vehicule(self):
        """Des arrivées simultanées sur une même voie sont introduites en file."""
        config = charger_scenario('S03')
        for event in config['arrivals']:
            event['scheduled_s'] = 0
        sim = Simulation(False, config)
        for _ in range(2400):
            sim.avancer()
            same_lane = sorted(v.s for v in sim.vehicules if v.trajet == 'O_E')
            self.assertTrue(all(b-a >= 55-1e-7 for a, b in zip(same_lane, same_lane[1:])))
            if sim.ambulance_terminee is not None:
                break
        self.assertEqual(len(sim.entrees), len(config['arrivals']))
        self.assertGreater(sim.ambulance_depart, 0)

    def test_s03_file_effective(self):
        """L'ambulance rejoint réellement au moins une voiture immobilisée."""
        for priority in (False, True):
            sim = Simulation(priority, charger_scenario('S03'))
            found = False
            for _ in range(2400):
                positions = {v.identifiant: v.s for v in sim.vehicules}
                sim.avancer()
                amb = next((v for v in sim.vehicules if v.ambulance), None)
                if amb:
                    found |= any(v.trajet == amb.trajet and v.s > amb.s and
                                 positions.get(v.identifiant) == v.s for v in sim.vehicules)
                if sim.ambulance_terminee is not None:
                    break
            self.assertTrue(found)

    def test_timeout_produit_interruption(self):
        """Une ambulance trop lente produit un essai incomplet à 120 secondes."""
        config = charger_scenario('S01')
        config['arrivals'][0]['speed_px_s'] = 0.1
        result = executer_essai(config, False, str(uuid4()), str(uuid4()))
        self.assertIsNone(result['duration_s'])
        self.assertEqual(result['events'][-1]['reason'], 'timeout')
        for event in result['events']:
            valider_evenement(event)

    def test_configuration_incompatible_refusee(self):
        """Les unités, versions et trajets non pris en charge ne sont pas ignorés."""
        for key, value in [('scenario_version', 1), ('step_s', 0.1)]:
            config = charger_scenario('S01')
            config[key] = value
            with self.assertRaises(ValueError):
                calendrier(config)
        config = charger_scenario('S01')
        config['arrivals'][0].update(route='S_N', branch='S')
        with self.assertRaises(ValueError):
            calendrier(config)
