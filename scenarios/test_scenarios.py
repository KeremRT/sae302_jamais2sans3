import unittest
from comparer_scenarios import charger_scenario, comparer, faire_essai, calculer_gain


class TestsScenarios(unittest.TestCase):

    def test_repetition(self):

        for nom in ('normal', 'dense', 'urgence'):
            scenario = charger_scenario(nom)
            premier = comparer(scenario)
            second = comparer(scenario)
            self.assertEqual(premier, second)
            for mode in ('SANS', 'AVEC'):
                essai = premier[mode]
                self.assertEqual(essai['etat'], 'TERMINE')
                self.assertAlmostEqual(essai['duree'], essai['arrivee'] - essai['depart'])

    def test_gain(self):

        self.assertEqual(calculer_gain({'duree': 18}, {'duree': 15}), 3)
        self.assertEqual(calculer_gain({'duree': 15}, {'duree': 18}), -3)
        self.assertEqual(calculer_gain({'duree': 15}, {'duree': 15}), 0)
        self.assertIsNone(calculer_gain({'duree': None}, {'duree': 15}))

    def test_interruption(self):

        scenario = charger_scenario('normal')
        scenario['duree_max'] = 1
        essai = faire_essai(scenario, False)
        self.assertEqual(essai['etat'], 'INTERROMPU')
        self.assertIsNone(essai['duree'])


if __name__ == '__main__':
    unittest.main()
