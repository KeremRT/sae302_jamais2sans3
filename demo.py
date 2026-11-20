"""Exemple de raccordement avec MariaDB ; aucun trafic n'est simule ici."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from sae_data import MesuresRepository, DonneesInvalides, ErreurStockage
from sae_data.connexion import creer_factory


def generer_evenement(essai, kind, time_s):
    """Construit un événement de test avec ses identifiants et son temps simulé."""
    event = dict(essai, protocol_version=1, event_id=str(uuid4()),
                 type=kind, sim_time_s=time_s)
    if kind in ('priority_departed', 'priority_arrived'):
        event['vehicle_id'] = 'A1'
    return event


def preparer_exemple(repo, config):
    """Valeurs fictives destinees uniquement a verifier la chaine de sauvegarde."""
    comparison_id = str(uuid4())
    repo.creer_comparaison(config, comparison_id, data_origin='EXEMPLE')
    departure = next(x['scheduled_s'] for x in config['arrivals'] if x['vehicle_id'] == 'A1')
    for mode, duration in (('SANS', 27.4), ('AVEC', 22.0)):
        essai = repo.ouvrir_essai(comparison_id, mode, str(uuid4()))
        for kind, t in (('trial_started', 0), ('priority_departed', departure),
                        ('priority_arrived', departure + duration)):
            repo.traiter_evenement(generer_evenement(essai, kind, t))
    return comparison_id


def main():
    """Crée ou relit une comparaison de démonstration dans MariaDB."""
    parser = argparse.ArgumentParser(description='Donnees EXEMPLE, pas une simulation reelle.')
    parser.add_argument('--config', default='config.ini')
    parser.add_argument('--scenario', choices=('S01', 'S02', 'S03'), default='S02')
    parser.add_argument('--lire', metavar='COMPARISON_ID', help='Relire sans creer de donnees.')
    args = parser.parse_args()
    try:
        repo = MesuresRepository(creer_factory(args.config))
        if args.lire:
            cid = args.lire
        else:
            file = Path(__file__).parent / 'scenarios' / f'{args.scenario}.json'
            config = json.loads(file.read_text(encoding='utf-8'))
            cid = preparer_exemple(repo, config)
        result = repo.lire_comparaison(cid)
        print(f"Origine : {result['data_origin']}")
        print(f"Comparaison : {cid} | Scenario : {result['scenario_id']}")
        for mode in ('SANS', 'AVEC'):
            trial = result['essais'].get(mode)
            if trial:
                duration = trial['duration_s']
                value = f'{duration:.2f} s' if duration is not None else 'non disponible'
                print(f"{mode} : {trial['status']} | duree : {value}")
        gain = result['gain_s']
        print(f'Gain : {gain:.2f} s' if gain is not None else 'Comparaison incomplete.')
        return 0
    except (DonneesInvalides, ErreurStockage, ValueError, OSError, KeyError) as exc:
        print(f'Echec : {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
