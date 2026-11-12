
import unittest
from math import hypot

from simulation import (
    Simulation,
    ControleFeux,
    TRAJETS,
    comparer
)


class TestSimulation(unittest.TestCase):

    def test_cinq_entrees(self):
        self.assertEqual(
            {v.feu for v in TRAJETS.values()},
            {'F1', 'F2', 'F3', 'F4', 'F5'}
        )

    def test_feux_compatibles(self):
        for priorite in (False, True):
            sim = Simulation(priorite)

            for _ in range(800):
                sim.avancer()

                feux = sim.controle.etats()

                verts = {
                    f for f, etat in feux.items()
                    if etat == 'vert'
                }

                self.assertIn(
                    verts,
                    (
                        {'F1', 'F3'},
                        {'F2', 'F4'},
                        {'F5'},
                        set()
                    )
                )

    def test_comparaison_reproductible(self):
        sans, avec, gain = comparer()

        self.assertGreater(sans, avec)

        self.assertAlmostEqual(
            sans - avec,
            gain,
            places=6
        )

        self.assertEqual(
            comparer(),
            (sans, avec, gain)
        )

    def test_aucun_chevauchement_entre_vehicules(self):
        # Test du scénario dans les deux modes
        for priorite in (False, True):
            sim = Simulation(priorite=priorite)

            for _ in range(900):
                sim.avancer()

                for i, vehicule in enumerate(sim.vehicules):
                    x, y, _ = vehicule.position()

                    for autre in sim.vehicules[i + 1:]:
                        xx, yy, _ = autre.position()

                        distance = hypot(
                            x - xx,
                            y - yy
                        )

                        self.assertGreaterEqual(
                            distance,
                            40.0,
                            (
                                f"Chevauchement "
                                f"{vehicule.identifiant}/"
                                f"{autre.identifiant} "
                                f"vers t={sim.t:.2f}s"
                            )
                        )

    def test_ambulance_et_voiture_tournante_au_rouge(self):
        # L'ambulance et une voiture
        # partagent la même voie à l'ouest.
        sim = Simulation(priorite=False)

        for _ in range(280):
            sim.avancer()

        ambulance = next(
            v for v in sim.vehicules
            if v.ambulance
        )

        voiture = next(
            v for v in sim.vehicules
            if v.identifiant == 'V-05'
        )

        self.assertEqual(
            sim.controle.etats()['F4'],
            'rouge'
        )

        self.assertAlmostEqual(
            ambulance.s,
            ambulance.chemin.ligne_arret - 12
        )

        self.assertGreaterEqual(
            ambulance.s - voiture.s,
            55.0 - 1e-6
        )

    def test_ambulance_s_arrete_au_rouge(self):
        sim = Simulation(priorite=False)

        for _ in range(180):
            sim.avancer()

        amb = next(
            v for v in sim.vehicules
            if v.ambulance
        )

        self.assertLessEqual(
            amb.s,
            amb.chemin.ligne_arret - 12 + 1e-5
        )


if __name__ == '__main__':
    unittest.main()
