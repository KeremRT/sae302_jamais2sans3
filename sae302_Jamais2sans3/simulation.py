
"""Moteur de simulation simplifié, indépendant de Qt.

SAÉ 3.02 — Jamais2sans3
Carrefour fictif inspiré du secteur Alsace/Semm/Fribourg à Colmar.
Aucun pilotage de signalisation réelle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, hypot, degrees
from typing import Optional


DT = 0.05  # Pas de calcul en secondes simulées


@dataclass(frozen=True)
class Trajet:
    nom: str
    feu: str
    points: tuple[tuple[float, float], ...]
    arret_point: int

    cumul: tuple[float, ...] = field(init=False)
    longueur: float = field(init=False)

    def __post_init__(self):
        distances = [0.0]

        for (x1, y1), (x2, y2) in zip(
            self.points[:-1],
            self.points[1:]
        ):
            distance = hypot(
                x2 - x1,
                y2 - y1
            )

            distances.append(
                distances[-1] + distance
            )

        object.__setattr__(
            self,
            'cumul',
            tuple(distances)
        )

        object.__setattr__(
            self,
            'longueur',
            distances[-1]
        )

    @property
    def ligne_arret(self) -> float:
        return self.cumul[self.arret_point]

    def position(
        self,
        s: float
    ) -> tuple[float, float, float]:

        s = max(
            0.0,
            min(s, self.longueur)
        )

        for i in range(len(self.points) - 1):
            s0 = self.cumul[i]
            s1 = self.cumul[i + 1]

            if s <= s1 or i == len(self.points) - 2:
                x0, y0 = self.points[i]
                x1, y1 = self.points[i + 1]

                p = (
                    0
                    if s1 <= s0
                    else (s - s0) / (s1 - s0)
                )

                x = x0 + (x1 - x0) * p
                y = y0 + (y1 - y0) * p

                angle = degrees(
                    atan2(
                        y1 - y0,
                        x1 - x0
                    )
                )

                return x, y, angle

        return (*self.points[-1], 0.0)


# Trajectoires du carrefour à cinq branches
TRAJETS = {
    'O_E': Trajet(
        'Ouest → Est',
        'F4',
        (
            (45, 396),
            (280, 396),
            (399, 396),
            (460, 396),
            (540, 396),
            (650, 396),
            (1020, 396)
        ),
        2
    ),

    'E_O': Trajet(
        'Est → Ouest',
        'F2',
        (
            (1005, 335),
            (715, 335),
            (625, 335),
            (545, 335),
            (420, 335),
            (38, 335)
        ),
        1
    ),

    'N_S': Trajet(
        'Nord → Sud',
        'F1',
        (
            (489, 0),
            (489, 252),
            (489, 315),
            (489, 440),
            (489, 650)
        ),
        1
    ),

    'S_N': Trajet(
        'Sud → Nord',
        'F3',
        (
            (559, 660),
            (559, 491),
            (559, 425),
            (559, 320),
            (559, 0)
        ),
        1
    ),

    'SO_E': Trajet(
        'Fribourg → Est',
        'F5',
        (
            (136, 670),
            (260, 572),
            (390, 475),
            (453, 426),
            (505, 400),
            (585, 396),
            (1020, 396)
        ),
        2
    ),

    'O_S': Trajet(
        'Ouest → Sud',
        'F4',
        (
            (45, 396),
            (280, 396),
            (399, 396),
            (449, 408),
            (480, 443),
            (489, 512),
            (489, 655)
        ),
        2
    ),

    'E_N': Trajet(
        'Est → Nord',
        'F2',
        (
            (1005, 335),
            (715, 335),
            (632, 335),
            (585, 319),
            (559, 265),
            (559, 0)
        ),
        1
    ),
}


@dataclass
class Vehicule:
    identifiant: str
    trajet: str
    couleur: str
    vitesse: float

    s: float = 0.0
    ambulance: bool = False

    @property
    def chemin(self) -> Trajet:
        return TRAJETS[self.trajet]

    def position(self) -> tuple[float, float, float]:
        return self.chemin.position(self.s)


# Scénario identique avec et sans priorité
#
# Format :
# (instant, identifiant, trajet, couleur, vitesse, ambulance)

SCENARIO = (
    (0.00, 'AMB-01', 'O_E', '#ffffff', 74.0, True),
    (0.00, 'V-01', 'N_S', '#2e9de6', 61.0, False),
    (0.80, 'V-02', 'S_N', '#e8ad4b', 62.0, False),
    (1.80, 'V-03', 'E_O', '#d96a69', 63.0, False),
    (3.50, 'V-04', 'SO_E', '#8ccba9', 58.0, False),
    (6.20, 'V-05', 'O_S', '#85a8ea', 63.0, False),
    (9.00, 'V-06', 'E_N', '#c49ae5', 58.0, False),
)


# Correction des véhicules qui partagent une même voie.
#
# O_E et O_S empruntent la même route avant
# de se séparer au niveau du carrefour.
#
# Même principe pour E_O et E_N.

LONGUEUR_VOIE_COMMUNE = {
    frozenset(('O_E', 'O_S')):
        TRAJETS['O_E'].ligne_arret,

    frozenset(('E_O', 'E_N')):
        TRAJETS['E_O'].ligne_arret,
}

DISTANCE_SECURITE = 55.0


def meme_file_devant(
    suiveur: Vehicule,
    leader: Vehicule
) -> bool:
    """Vérifie si deux véhicules partagent la même file."""

    if suiveur.trajet == leader.trajet:
        return True

    separation = LONGUEUR_VOIE_COMMUNE.get(
        frozenset((
            suiveur.trajet,
            leader.trajet
        ))
    )

    return (
        separation is not None
        and leader.s <= separation + DISTANCE_SECURITE
    )


class ControleFeux:
    """Gestion locale des cycles et de la priorité ambulance.

    F2 + F4 : axe Est-Ouest
    F1 + F3 : axe Nord-Sud
    F5 : branche Sud-Ouest
    """

    CYCLE = (
        (8.0, 'NS', 'vert'),
        (1.5, 'NS', 'orange'),
        (1.0, 'AUCUN', 'rouge'),

        (4.5, 'SO', 'vert'),
        (1.0, 'SO', 'orange'),
        (1.0, 'AUCUN', 'rouge'),

        (8.0, 'EO', 'vert'),
        (1.5, 'EO', 'orange'),
        (1.0, 'AUCUN', 'rouge'),
    )

    DUREE_CYCLE = sum(
        temps for temps, _, _ in CYCLE
    )

    def __init__(self, priorite: bool):
        self.priorite = priorite
        self.cycle_t = 0.0

        self.etape = 'normal'
        self.etape_t = 0.0

        self.ancien_axe = 'AUCUN'
        self.deja_demande = False

        self.evenement: Optional[str] = None

    def phase_normale(self):
        t = self.cycle_t % self.DUREE_CYCLE

        for duree, axe, etat in self.CYCLE:
            if t < duree:
                return axe, etat

            t -= duree

        return 'AUCUN', 'rouge'

    def debut_priorite(self):
        if (
            not self.priorite
            or self.deja_demande
            or self.etape != 'normal'
        ):
            return

        self.deja_demande = True

        self.ancien_axe, _ = self.phase_normale()

        self.etape = 'orange'
        self.etape_t = 0.0

        self.evenement = (
            'Ambulance détectée : préparation de priorité'
        )

    def etats(self) -> dict[str, str]:
        if self.etape == 'normal':
            axe, couleur = self.phase_normale()

        elif self.etape == 'orange':
            axe = self.ancien_axe
            couleur = 'orange'

        elif self.etape in ('securite', 'retour'):
            axe = 'AUCUN'
            couleur = 'rouge'

        else:
            axe = 'EO'
            couleur = 'vert'

        actifs = {
            'EO': ('F2', 'F4'),
            'NS': ('F1', 'F3'),
            'SO': ('F5',),
            'AUCUN': (),
        }[axe]

        etats = {
            f'F{n}': 'rouge'
            for n in range(1, 6)
        }

        for feu in actifs:
            etats[feu] = couleur

        return etats

    def avancer(
        self,
        dt: float,
        ambulance_degagee: bool = False
    ):
        self.evenement = None

        if self.etape == 'normal':
            self.cycle_t = (
                self.cycle_t + dt
            ) % self.DUREE_CYCLE

            return

        self.etape_t += dt

        if (
            self.etape == 'orange'
            and self.etape_t >= 1.5
        ):
            self.etape = 'securite'
            self.etape_t = 0.0

            self.evenement = (
                'Tous les feux au rouge : '
                'dégagement du carrefour'
            )

        elif (
            self.etape == 'securite'
            and self.etape_t >= 1.0
        ):
            self.etape = 'priorite'
            self.etape_t = 0.0

            self.evenement = (
                'Priorité accordée sur l’axe ouest-est'
            )

        elif (
            self.etape == 'priorite'
            and ambulance_degagee
        ):
            self.etape = 'retour'
            self.etape_t = 0.0

            self.evenement = (
                'Ambulance sortie de la zone de conflit'
            )

        elif (
            self.etape == 'retour'
            and self.etape_t >= 1.0
        ):
            self.etape = 'normal'
            self.etape_t = 0.0
            self.cycle_t = 0.0

            self.evenement = (
                'Retour au cycle normal'
            )

    @property
    def nom_phase(self) -> str:
        return {
            'normal':
                f"Cycle normal : {self.phase_normale()[0]}",

            'orange':
                'Transition orange',

            'securite':
                'Dégagement : tous rouges',

            'priorite':
                'Priorité ambulance : Ouest → Est',

            'retour':
                'Retour sécurisé : tous rouges',
        }[self.etape]


class Simulation:
    def __init__(self, priorite: bool = True):
        self.priorite = priorite
        self.t = 0.0

        self.vehicules: list[Vehicule] = []
        self.controle = ControleFeux(priorite)

        self.index_scenario = 0

        self.ambulance_terminee: Optional[float] = None
        self.ambulance_degagee = False

        self.journal: list[str] = [
            'Simulation prête (modèle local, sans serveur réseau)'
        ]

    def ajouter_evenement(self, message: str):
        self.journal.append(
            f'{self.t:05.1f} s · {message}'
        )

        self.journal = self.journal[-12:]

    def avancer(self, dt: float = DT):
        if self.ambulance_terminee is not None:
            return

        self.t += dt

        # Ajouter les véhicules programmés
        while (
            self.index_scenario < len(SCENARIO)
            and SCENARIO[self.index_scenario][0]
            <= self.t + 1e-8
        ):
            (
                _,
                identifiant,
                trajet,
                couleur,
                vitesse,
                ambulance
            ) = SCENARIO[self.index_scenario]

            self.vehicules.append(
                Vehicule(
                    identifiant,
                    trajet,
                    couleur,
                    vitesse,
                    ambulance=ambulance
                )
            )

            self.index_scenario += 1

            if ambulance:
                self.ajouter_evenement(
                    'Ambulance entrée dans le scénario'
                )

        amb = next(
            (
                v for v in self.vehicules
                if v.ambulance
            ),
            None
        )

        # Détection locale de l'ambulance
        if (
            amb
            and not self.controle.deja_demande
            and self.priorite
        ):
            distance = (
                amb.chemin.ligne_arret - amb.s
            )

            if 0 < distance <= 190:
                self.controle.debut_priorite()

                if self.controle.evenement:
                    self.ajouter_evenement(
                        self.controle.evenement
                    )

        feux = self.controle.etats()

        # Déplacement de tous les véhicules
        for v in self.vehicules:
            trajet = v.chemin

            cible = min(
                trajet.longueur,
                v.s + v.vitesse * dt
            )

            # Arrêt au rouge ou à l'orange
            if (
                v.s <= trajet.ligne_arret - 12 + 1e-7
                and feux[trajet.feu] != 'vert'
            ):
                cible = min(
                    cible,
                    trajet.ligne_arret - 12
                )

            # Empêcher le chevauchement des véhicules
            # qui empruntent la même voie, même si leurs
            # destinations sont différentes.
            vehicules_devant = [
                autre.s
                for autre in self.vehicules
                if (
                    autre is not v
                    and autre.s > v.s
                    and meme_file_devant(v, autre)
                )
            ]

            if vehicules_devant:
                cible = min(
                    cible,
                    min(vehicules_devant)
                    - DISTANCE_SECURITE
                )

            v.s = max(
                v.s,
                cible
            )

        if amb is not None:
            x, _, _ = amb.position()

            # Passage au-delà de la zone centrale
            if x >= 745:
                self.ambulance_degagee = True

            # Arrivée de l'ambulance
            if (
                amb.s >= amb.chemin.longueur - 15
                and self.ambulance_terminee is None
            ):
                self.ambulance_terminee = self.t

                self.ajouter_evenement(
                    f'Ambulance arrivée : {self.t:.2f} s'
                )

        # Actualisation des feux
        self.controle.avancer(
            dt,
            self.ambulance_degagee
        )

        if self.controle.evenement:
            self.ajouter_evenement(
                self.controle.evenement
            )

        # Retirer les véhicules sortis du carrefour
        # en conservant l'ambulance.
        self.vehicules = [
            v for v in self.vehicules
            if (
                v.ambulance
                or v.s < v.chemin.longueur - 5
            )
        ]


def comparer() -> tuple[float, float, float]:
    """Comparaison avec et sans priorité."""

    temps = []

    for priorite in (False, True):
        sim = Simulation(priorite)

        # Maximum 200 secondes simulées
        for _ in range(4000):
            sim.avancer()

            if sim.ambulance_terminee is not None:
                temps.append(
                    sim.ambulance_terminee
                )
                break

        else:
            raise RuntimeError(
                'Le scénario ne s’est pas terminé '
                'avant 200 secondes.'
            )

    sans, avec = temps

    gain = sans - avec

    return sans, avec, gain
