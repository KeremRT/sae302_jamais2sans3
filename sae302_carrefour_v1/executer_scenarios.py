"""Exécute les scénarios locaux et sauvegarde facultativement dans MariaDB.

Ce raccordement direct sert à la validation. Il ne remplace pas le serveur TCP.
"""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from scenarios_loader import charger_scenario
from simulation import Simulation, DT


def executer_essai(config, priorite, comparison_id, trial_id):
    """Produit les événements du protocole v1 depuis les mesures du moteur."""
    sim = Simulation(priorite, config)
    base = dict(protocol_version=1, comparison_id=comparison_id, trial_id=trial_id,
                scenario_id=config['scenario_id'], scenario_version=config['scenario_version'],
                mode='AVEC' if priorite else 'SANS')
    events = []

    def emit(kind, t, **extra):
        """Attribue un UUID à chaque événement mesuré, sans heure système."""
        events.append(dict(base, event_id=str(uuid4()), type=kind,
                           sim_time_s=round(t, 6), **extra))

    emit('trial_started', 0)
    departed = False
    for _ in range(round(config['max_sim_time_s'] / DT)):
        sim.avancer()
        if sim.ambulance_depart is not None and not departed:
            emit('priority_departed', sim.ambulance_depart, vehicle_id='A1')
            departed = True
        if sim.ambulance_terminee is not None:
            emit('priority_arrived', sim.ambulance_terminee, vehicle_id='A1')
            break
    else:
        emit('trial_interrupted', 120, reason='timeout')
    duration = (round(sim.ambulance_terminee - sim.ambulance_depart, 6)
                if sim.ambulance_terminee is not None else None)
    return dict(mode=base['mode'], trial_id=trial_id, duration_s=duration,
                status='TERMINE' if duration is not None else 'INTERROMPU',
                events=events, entries=sim.entrees)


def executer_comparaison(config, repo=None):
    """Rejoue la même configuration, avec identifiants distincts pour les essais."""
    cid = str(uuid4())
    if repo is not None:
        repo.creer_comparaison(config, cid, data_origin='SIMULATION')
    trials = []
    for priorite in (False, True):
        tid = str(uuid4())
        if repo is not None:
            repo.ouvrir_essai(cid, 'AVEC' if priorite else 'SANS', tid)
        trial = executer_essai(config, priorite, cid, tid)
        if repo is not None:
            for event in trial['events']:
                repo.traiter_evenement(event)
        trials.append(trial)
    sans, avec = (t['duration_s'] for t in trials)
    gain = round(sans - avec, 6) if sans is not None and avec is not None else None
    if repo is not None:
        saved = repo.lire_comparaison(cid)
        expected = None if gain is None else str(gain)
        from decimal import Decimal
        if saved['gain_s'] != (None if expected is None else Decimal(expected)):
            raise RuntimeError('Résultat MariaDB différent du résultat simulé.')
    return dict(comparison_id=cid, scenario_id=config['scenario_id'],
                scenario_version=config['scenario_version'], data_origin='SIMULATION',
                controller='local_without_tcp', configuration=config,
                trials=trials, gain_s=gain, saved_to_mariadb=repo is not None)


def main():
    """Exporte les résultats et active MariaDB seulement sur demande explicite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['S01', 'S02', 'S03', 'tous'], default='tous')
    parser.add_argument('--config', help='Configuration MariaDB privée ; sinon aucune écriture SQL')
    parser.add_argument('--output', default='resultats_locaux/comparaisons.json')
    args = parser.parse_args()
    repo = None
    if args.config:
        from sae_data import MesuresRepository
        from sae_data.connexion import creer_factory
        repo = MesuresRepository(creer_factory(args.config))
    ids = ['S01', 'S02', 'S03'] if args.scenario == 'tous' else [args.scenario]
    results = [executer_comparaison(charger_scenario(sid), repo) for sid in ids]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for result in results:
        print(result['scenario_id'], [(t['mode'], t['duration_s']) for t in result['trials']],
              'gain:', result['gain_s'], 'MariaDB:', result['saved_to_mariadb'])


if __name__ == '__main__':
    main()
