import unittest
from simulation import Simulation, ControleFeux, TRAJETS, comparer

class TestSimulation(unittest.TestCase):
    """Vérifie les propriétés du moteur local et de ses feux."""
    def test_cinq_entrees(self):
        """Vérifie que les trajets utilisent les cinq feux du carrefour."""
        self.assertEqual({v.feu for v in TRAJETS.values()}, {'F1','F2','F3','F4','F5'})

    def test_feux_compatibles(self):
        """Vérifie que seuls les groupes de feux autorisés passent simultanément au vert."""
        for priorite in (False,True):
            sim=Simulation(priorite)
            for _ in range(800):
                sim.avancer()
                feux=sim.controle.etats()
                verts={f for f,e in feux.items() if e=='vert'}
                self.assertIn(verts, ({'F1','F3'}, {'F2','F4'}, {'F5'}, set()))

    def test_comparaison_reproductible(self):
        """Vérifie la répétabilité des durées et le calcul du gain."""
        sans,avec,gain=comparer()
        self.assertGreater(sans,avec)
        self.assertAlmostEqual(sans-avec,gain,places=6)
        self.assertEqual(comparer(), (sans,avec,gain))

    def test_ambulance_s_arrete_au_rouge(self):
        """Vérifie que l’ambulance sans priorité respecte sa ligne d’arrêt."""
        sim=Simulation(priorite=False)
        for _ in range(180):
            sim.avancer()
        amb=next(v for v in sim.vehicules if v.ambulance)
        self.assertLessEqual(amb.s,amb.chemin.ligne_arret-12+1e-5)

if __name__ == '__main__':
    unittest.main()
