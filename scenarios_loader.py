"""Chargement des scénarios version 2 adaptés au moteur cinq branches."""

import copy
import json
import math
from pathlib import Path

from sae_data.validation import valider_config


def modele_courant():
    """Décrit les paramètres effectifs afin de détecter une configuration périmée."""
    from simulation import TRAJETS, ControleFeux
    return {
        'geometry': {'branches': ['N', 'S', 'E', 'O', 'SO'], 'unit': 'pixel',
                     'routes': {key: {'points': [list(p) for p in route.points],
                                      'stop_index': route.arret_point, 'light': route.feu}
                                for key, route in TRAJETS.items()}},
        'vehicles': {'reference_point': 'center', 'gap_px': 55,
                     'motion': 'constant_speed_without_acceleration'},
        'lights': {'phases': [list(phase) for phase in ControleFeux.CYCLE]},
        'priority': {'vehicle_id': 'A1', 'route': ['O', 'E'],
                     'request_distance_px': 190, 'amber_s': 1.5,
                     'all_red_s': 1.0, 'exit_x_px': 745,
                     'controller': 'local_pedagogical'},
        'step_s': 0.05, 'max_sim_time_s': 120,
        'initial_vehicles': [],
        'blocked_entry_policy': 'wait_outside_and_log_effective_entry',
    }


def calendrier(config):
    """Valide les paramètres et convertit les arrivées sans modifier l'original."""
    from simulation import TRAJETS
    config = copy.deepcopy(config)
    valider_config(config)
    if config['scenario_version'] != 2:
        raise ValueError('Le moteur cinq branches nécessite scenario_version=2.')
    for key, value in modele_courant().items():
        if config.get(key) != value:
            raise ValueError(f'Paramètre incompatible avec le moteur : {key}')
    rows = []
    for event in config['arrivals']:
        route = event.get('route')
        speed = event.get('speed_px_s')
        if route not in TRAJETS or event['branch'] != route.split('_')[0]:
            raise ValueError('Trajet ou branche incompatible.')
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 100:
            raise ValueError('Vitesse attendue dans ]0,100] pixels/s.')
        if abs(event['scheduled_s'] / 0.05 - round(event['scheduled_s'] / 0.05)) > 1e-7:
            raise ValueError('Arrivée non alignée sur le pas fixe.')
        ambulance = event['vehicle_id'] == 'A1'
        if event.get('kind') != ('emergency' if ambulance else 'ordinary'):
            raise ValueError('Type de véhicule incohérent.')
        if ambulance and route != 'O_E':
            raise ValueError('Le contrôleur local donne la priorité à O_E uniquement.')
        rows.append((event['scheduled_s'], event['vehicle_id'], route,
                     '#ffffff' if ambulance else '#2e9de6', speed, ambulance))
    return tuple(sorted(rows, key=lambda row: row[0]))


def charger_scenario(identifiant):
    """Charge S01, S02 ou S03 depuis les fichiers JSON versionnés."""
    if identifiant not in ('S01', 'S02', 'S03'):
        raise ValueError('Scénario inconnu.')
    path = Path(__file__).parent / 'scenarios' / f'{identifiant}.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    calendrier(config)
    return config
