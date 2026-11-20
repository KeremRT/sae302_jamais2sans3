import copy
import json
import math
from pathlib import Path

from sae_data.validation import valider_config


# On rassemble les réglages du moteur pour les comparer à ceux du scénario.
def modele_courant():
    from simulation import TRAJETS, ControleFeux

    # Pour chaque trajet, on garde ses points, son point d'arrêt et son feu.
    routes = {}
    for nom, trajet in TRAJETS.items():
        points = []
        # On convertit chaque couple de coordonnées en liste, comme dans le JSON.
        for point in trajet.points:
            points.append(list(point))
        routes[nom] = {
            'points': points,
            'stop_index': trajet.arret_point,
            'light': trajet.feu,
        }

    # On recopie les phases des feux dans l'ordre du cycle.
    phases = []
    for phase in ControleFeux.CYCLE:
        phases.append(list(phase))

    return {
        'geometry': {'branches': ['N', 'S', 'E', 'O', 'SO'], 'unit': 'pixel',
                     'routes': routes},
        'vehicles': {'reference_point': 'center', 'gap_px': 55,
                     'motion': 'constant_speed_without_acceleration'},
        'lights': {'phases': phases},
        'priority': {'vehicle_id': 'A1', 'route': ['O', 'E'],
                     'request_distance_px': 190, 'amber_s': 1.5,
                     'all_red_s': 1.0, 'exit_x_px': 745,
                     'controller': 'local_pedagogical'},
        'step_s': 0.05, 'max_sim_time_s': 120,
        'initial_vehicles': [],
        'blocked_entry_policy': 'wait_outside_and_log_effective_entry',
    }


# On vérifie le scénario puis on prépare les arrivées pour la simulation.
def calendrier(config):
    from simulation import TRAJETS
    # On travaille sur une copie et on vérifie les réglages du carrefour.
    config = copy.deepcopy(config)
    valider_config(config)
    if config['scenario_version'] != 2:
        raise ValueError('Le moteur cinq branches nécessite scenario_version=2.')
    for key, value in modele_courant().items():
        if config.get(key) != value:
            raise ValueError(f'Paramètre incompatible avec le moteur : {key}')
    # Pour chaque véhicule, on vérifie que le trajet, la branche et la vitesse vont ensemble.
    rows = []
    for event in config['arrivals']:
        route = event.get('route')
        speed = event.get('speed_px_s')
        if route not in TRAJETS or event['branch'] != route.split('_')[0]:
            raise ValueError('Trajet ou branche incompatible.')
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 100:
            raise ValueError('Vitesse attendue dans ]0,100] pixels/s.')
        # L'heure d'arrivée doit tomber sur un pas de 0,05 seconde.
        nombre_pas = event['scheduled_s'] / 0.05
        ecart = abs(nombre_pas - round(nombre_pas))
        if ecart > 0.0000001:
            raise ValueError('Arrivée non alignée sur le pas fixe.')
        # On reconnaît l'ambulance avec A1 pour choisir sa couleur et vérifier son trajet.
        ambulance = event['vehicle_id'] == 'A1'
        if ambulance:
            type_attendu = 'emergency'
            couleur = '#ffffff'
        else:
            type_attendu = 'ordinary'
            couleur = '#2e9de6'
        if event.get('kind') != type_attendu:
            raise ValueError('Type de véhicule incohérent.')
        if ambulance and route != 'O_E':
            raise ValueError('Le contrôleur local donne la priorité à O_E uniquement.')
        rows.append((event['scheduled_s'], event['vehicle_id'], route,
                     couleur, speed, ambulance))

    # On trie les véhicules par heure d'arrivée avant de renvoyer le calendrier.
    rows.sort(key=heure_arrivee)
    return tuple(rows)


# On lit le JSON choisi et on le vérifie avant de renvoyer sa configuration.
def charger_scenario(identifiant):
    if identifiant not in ('S01', 'S02', 'S03'):
        raise ValueError('Scénario inconnu.')
    path = Path(__file__).parent / 'scenarios' / f'{identifiant}.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    calendrier(config)
    return config


# Le tri utilise le premier élément de chaque arrivée, qui contient l'heure.
def heure_arrivee(arrivee):
    return arrivee[0]
