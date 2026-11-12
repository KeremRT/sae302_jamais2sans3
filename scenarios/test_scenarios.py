"""Tests du protocole de comparaison sans modifier le moteur partagé."""
import copy
import unittest
from comparer_scenarios import charger, executer, comparer

class ScenariosTests(unittest.TestCase):
    """Vérifie la reproductibilité, le chrono et l'interruption."""
    def test_reproductibilite(self):
        """Deux répétitions donnent les mêmes mesures sans muter la configuration."""
        for name in ('normal','dense','urgence'):
            c=charger(name); avant=copy.deepcopy(c)
            a=comparer(c);b=comparer(c)
            self.assertEqual(c,avant)
            self.assertNotEqual(a['comparison_id'],b['comparison_id'])
            for mode in ('SANS','AVEC'):
                x=a['essais'][mode];y=b['essais'][mode]
                self.assertEqual(x['duration_s'],y['duration_s'])
                self.assertAlmostEqual(x['duration_s'],x['arrival_s']-x['departure_s'])
            self.assertAlmostEqual(a['gain_s'],a['essais']['SANS']['duration_s']-a['essais']['AVEC']['duration_s'])

    def test_interruption(self):
        """Un arrêt avant l'arrivée ne produit pas de durée terminée."""
        r=executer(charger('normal'),False,limite=1)
        self.assertEqual(r['status'],'INTERROMPU')
        self.assertIsNone(r['duration_s'])
        self.assertIsNone(r['arrival_s'])

if __name__=='__main__':
    unittest.main()
