import json
from decimal import Decimal, InvalidOperation
from uuid import UUID


# Cette erreur indique qu’un message ou un scénario contient une donnée incorrecte.
class DonneesInvalides(ValueError):
    pass


# On vérifie le format de l’identifiant.
def uuid4_valide(value, champ):
    if not isinstance(value, str):
        raise DonneesInvalides(f'{champ} doit etre une chaine UUID v4.')
    try:
        identifiant_lu = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise DonneesInvalides(f'{champ} invalide.') from exc
    if identifiant_lu.version != 4:
        raise DonneesInvalides(f'{champ} doit etre un UUID v4 canonique en minuscules.')
    if str(identifiant_lu) != value:
        raise DonneesInvalides(f'{champ} doit etre un UUID v4 canonique en minuscules.')
    return value


# On écrit le JSON toujours de la même façon pour pouvoir le comparer.
def json_canonique(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise DonneesInvalides('Donnees non serialisables en JSON valide.') from exc


# On vérifie que le temps est compris entre 0 et 120 secondes et assez précis pour la base.
def temps_valide(value):
    # On exige un nombre et on écarte les booléens comme True.
    if type(value) not in (int, float, Decimal):
        raise DonneesInvalides('sim_time_s doit etre un nombre, pas une chaine.')
    try:
        temps = Decimal(str(value))
        if not temps.is_finite():
            raise DonneesInvalides('sim_time_s doit etre fini et compris entre 0 et 120 s.')
        if temps < 0:
            raise DonneesInvalides('sim_time_s doit etre fini et compris entre 0 et 120 s.')
        if temps > 120:
            raise DonneesInvalides('sim_time_s doit etre fini et compris entre 0 et 120 s.')
        precision = Decimal('0.000001')
        temps_six_decimales = temps.quantize(precision)
        if temps != temps_six_decimales:
            raise DonneesInvalides('Precision maximale : six decimales, sans arrondi implicite.')
    except InvalidOperation as exc:
        raise DonneesInvalides('Temps invalide.') from exc
    return temps


# On vérifie les champs du message avant de l’enregistrer.
def valider_evenement(message):
    if not isinstance(message, dict):
        raise DonneesInvalides('Un evenement doit etre un objet JSON.')
    # On prépare la liste des champs que le message doit contenir.
    champs_obligatoires = [
        'protocol_version', 'event_id', 'type', 'comparison_id', 'trial_id',
        'scenario_id', 'scenario_version', 'mode', 'sim_time_s',
    ]
    champs_facultatifs = ['vehicle_id', 'reason']

    for champ in champs_obligatoires:
        if champ not in message:
            raise DonneesInvalides('Champs obligatoires absents ou champs inconnus.')

    champs_autorises = champs_obligatoires + champs_facultatifs
    for champ in message:
        if champ not in champs_autorises:
            raise DonneesInvalides('Champs obligatoires absents ou champs inconnus.')
    if type(message['protocol_version']) is not int:
        raise DonneesInvalides('Version de protocole non prise en charge.')
    if message['protocol_version'] != 1:
        raise DonneesInvalides('Version de protocole non prise en charge.')
    if type(message['scenario_version']) is not int:
        raise DonneesInvalides('Version de scenario invalide.')
    if message['scenario_version'] < 1:
        raise DonneesInvalides('Version de scenario invalide.')
    # On contrôle les trois identifiants qui relient le message à son essai.
    for champ in ('event_id', 'trial_id', 'comparison_id'):
        uuid4_valide(message[champ], champ)
    if not isinstance(message['scenario_id'], str):
        raise DonneesInvalides('Scenario inconnu.')
    if message['scenario_id'] not in ('S01', 'S02', 'S03'):
        raise DonneesInvalides('Scenario inconnu.')
    if not isinstance(message['mode'], str):
        raise DonneesInvalides('Mode attendu : AVEC ou SANS.')
    if message['mode'] not in ('AVEC', 'SANS'):
        raise DonneesInvalides('Mode attendu : AVEC ou SANS.')
    # On vérifie les règles propres au type d’événement reçu.
    type_evenement = message['type']
    if not isinstance(type_evenement, str):
        raise DonneesInvalides('Type d evenement inconnu.')
    if type_evenement not in ('trial_started', 'priority_departed', 'priority_arrived', 'trial_interrupted'):
        raise DonneesInvalides('Type d evenement inconnu.')
    if type_evenement in ('priority_departed', 'priority_arrived'):
        if message.get('vehicle_id') != 'A1':
            raise DonneesInvalides('Depart/arrivee : vehicle_id=A1 requis, reason interdit.')
        if 'reason' in message:
            raise DonneesInvalides('Depart/arrivee : vehicle_id=A1 requis, reason interdit.')
    elif 'vehicle_id' in message:
        raise DonneesInvalides('vehicle_id est reserve aux evenements de A1.')
    if type_evenement == 'trial_interrupted':
        if message.get('reason') not in ('user_stop', 'timeout', 'connection_lost'):
            raise DonneesInvalides('Motif d interruption invalide.')
    elif 'reason' in message:
        raise DonneesInvalides('reason est reserve aux interruptions.')
    # On contrôle le temps simulé avant de préparer le message pour la base.
    temps = temps_valide(message['sim_time_s'])
    if type_evenement == 'trial_started':
        if temps != 0:
            raise DonneesInvalides('Le lancement doit etre a t=0.')
    if type_evenement == 'trial_interrupted':
        if message['reason'] == 'timeout':
            if temps != 120:
                raise DonneesInvalides('Le timeout du scenario doit etre a t=120 s.')
    normalise = message.copy()
    normalise['sim_time_s'] = float(temps)
    json_message = json_canonique(normalise)
    message_octets = json_message.encode('utf-8')
    taille_message = len(message_octets)
    if taille_message > 16384:
        raise DonneesInvalides('Message trop volumineux.')
    return normalise, temps, json_message


# On contrôle les réglages du scénario et la liste des véhicules.
def valider_config(config):
    if not isinstance(config, dict):
        raise DonneesInvalides('La configuration doit etre un objet.')
    if config.get('scenario_id') not in ('S01', 'S02', 'S03'):
        raise DonneesInvalides('Scenario inconnu.')
    version = config.get('scenario_version')
    if type(version) is not int:
        raise DonneesInvalides('Version de scenario invalide.')
    if version < 1:
        raise DonneesInvalides('Version de scenario invalide.')
    for champ in ('geometry', 'vehicles', 'lights', 'priority', 'arrivals'):
        if champ not in config:
            raise DonneesInvalides(f'Configuration incomplete : {champ}.')
    if config.get('max_sim_time_s') != 120:
        raise DonneesInvalides('Cette version du module attend une limite de 120 s.')
    if not isinstance(config['arrivals'], list):
        raise DonneesInvalides('arrivals doit etre une liste.')
    # On garde les identifiants déjà vus pour repérer les doublons.
    identifiants = []
    for arrivee in config['arrivals']:
        if not isinstance(arrivee, dict):
            raise DonneesInvalides('Arrivee invalide.')
        if not isinstance(arrivee.get('vehicle_id'), str):
            raise DonneesInvalides('Arrivee invalide.')
        if arrivee['vehicle_id'] in identifiants:
            raise DonneesInvalides('Vehicule duplique ou branche inconnue.')
        if arrivee.get('branch') not in ('N', 'S', 'E', 'O'):
            raise DonneesInvalides('Vehicule duplique ou branche inconnue.')
        identifiants.append(arrivee['vehicle_id'])
        temps_valide(arrivee.get('scheduled_s'))
    if 'A1' not in identifiants:
        raise DonneesInvalides('Le calendrier doit contenir A1.')
    return json_canonique(config)
