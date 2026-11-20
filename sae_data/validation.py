"""Validation du protocole version 1. Aucune dependance externe."""

import json
from decimal import Decimal, InvalidOperation
from uuid import UUID


class DonneesInvalides(ValueError):
    """Erreur de format ou de coherence metier ; message non enregistre."""


def uuid4_valide(value, champ):
    """Vérifie qu’une valeur est un UUID version 4 sous sa forme canonique."""
    if not isinstance(value, str):
        raise DonneesInvalides(f'{champ} doit etre une chaine UUID v4.')
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise DonneesInvalides(f'{champ} invalide.') from exc
    if parsed.version != 4 or str(parsed) != value:
        raise DonneesInvalides(f'{champ} doit etre un UUID v4 canonique en minuscules.')
    return value


def json_canonique(value):
    """Sérialise les données de manière stable pour comparer leurs configurations."""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise DonneesInvalides('Donnees non serialisables en JSON valide.') from exc


def temps_valide(value):
    # bool est un sous-type de int en Python : le rejeter explicitement.
    """Vérifie un temps simulé entre zéro et 120 secondes avec six décimales au plus."""
    if type(value) not in (int, float, Decimal):
        raise DonneesInvalides('sim_time_s doit etre un nombre, pas une chaine.')
    try:
        t = Decimal(str(value))
        if not t.is_finite() or t < 0 or t > 120:
            raise DonneesInvalides('sim_time_s doit etre fini et compris entre 0 et 120 s.')
        if t != t.quantize(Decimal('0.000001')):
            raise DonneesInvalides('Precision maximale : six decimales, sans arrondi implicite.')
    except InvalidOperation as exc:
        raise DonneesInvalides('Temps invalide.') from exc
    return t


def valider_evenement(message):
    """Valide les champs d’un événement et renvoie ses données normalisées."""
    if not isinstance(message, dict):
        raise DonneesInvalides('Un evenement doit etre un objet JSON.')
    required = {'protocol_version', 'event_id', 'type', 'comparison_id', 'trial_id',
                'scenario_id', 'scenario_version', 'mode', 'sim_time_s'}
    if not required.issubset(message) or set(message) - required - {'vehicle_id', 'reason'}:
        raise DonneesInvalides('Champs obligatoires absents ou champs inconnus.')
    if type(message['protocol_version']) is not int or message['protocol_version'] != 1:
        raise DonneesInvalides('Version de protocole non prise en charge.')
    if type(message['scenario_version']) is not int or message['scenario_version'] < 1:
        raise DonneesInvalides('Version de scenario invalide.')
    # Ces identifiants empêchent de mélanger les comparaisons et les essais.
    for key in ('event_id', 'trial_id', 'comparison_id'):
        uuid4_valide(message[key], key)
    if not isinstance(message['scenario_id'], str) or message['scenario_id'] not in ('S01', 'S02', 'S03'):
        raise DonneesInvalides('Scenario inconnu.')
    if not isinstance(message['mode'], str) or message['mode'] not in ('AVEC', 'SANS'):
        raise DonneesInvalides('Mode attendu : AVEC ou SANS.')
    kind = message['type']
    if not isinstance(kind, str) or kind not in (
            'trial_started', 'priority_departed', 'priority_arrived', 'trial_interrupted'):
        raise DonneesInvalides('Type d evenement inconnu.')
    if kind in ('priority_departed', 'priority_arrived'):
        if message.get('vehicle_id') != 'A1' or 'reason' in message:
            raise DonneesInvalides('Depart/arrivee : vehicle_id=A1 requis, reason interdit.')
    elif 'vehicle_id' in message:
        raise DonneesInvalides('vehicle_id est reserve aux evenements de A1.')
    if kind == 'trial_interrupted':
        if message.get('reason') not in ('user_stop', 'timeout', 'connection_lost'):
            raise DonneesInvalides('Motif d interruption invalide.')
    elif 'reason' in message:
        raise DonneesInvalides('reason est reserve aux interruptions.')
    t = temps_valide(message['sim_time_s'])
    if kind == 'trial_started' and t != 0:
        raise DonneesInvalides('Le lancement doit etre a t=0.')
    if kind == 'trial_interrupted' and message['reason'] == 'timeout' and t != 120:
        raise DonneesInvalides('Le timeout du scenario doit etre a t=120 s.')
    normalise = dict(message, sim_time_s=float(t))
    canonical = json_canonique(normalise)
    if len(canonical.encode('utf-8')) > 16384:
        raise DonneesInvalides('Message trop volumineux.')
    return normalise, t, canonical


def valider_config(config):
    """Vérifie la configuration du scénario et renvoie sa représentation JSON stable."""
    if not isinstance(config, dict):
        raise DonneesInvalides('La configuration doit etre un objet.')
    if config.get('scenario_id') not in ('S01', 'S02', 'S03'):
        raise DonneesInvalides('Scenario inconnu.')
    v = config.get('scenario_version')
    if type(v) is not int or v < 1:
        raise DonneesInvalides('Version de scenario invalide.')
    for key in ('geometry', 'vehicles', 'lights', 'priority', 'arrivals'):
        if key not in config:
            raise DonneesInvalides(f'Configuration incomplete : {key}.')
    if config.get('max_sim_time_s') != 120:
        raise DonneesInvalides('Cette version du module attend une limite de 120 s.')
    if not isinstance(config['arrivals'], list):
        raise DonneesInvalides('arrivals doit etre une liste.')
    ids = set()
    for item in config['arrivals']:
        if not isinstance(item, dict) or not isinstance(item.get('vehicle_id'), str):
            raise DonneesInvalides('Arrivee invalide.')
        if item['vehicle_id'] in ids or item.get('branch') not in ('N', 'S', 'E', 'O'):
            raise DonneesInvalides('Vehicule duplique ou branche inconnue.')
        ids.add(item['vehicle_id'])
        temps_valide(item.get('scheduled_s'))
    if 'A1' not in ids:
        raise DonneesInvalides('Le calendrier doit contenir A1.')
    return json_canonique(config)
