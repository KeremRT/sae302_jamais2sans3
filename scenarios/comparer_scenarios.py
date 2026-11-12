"""Comparaisons reproductibles avec le moteur de Kerem, sans modifier ses fichiers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sql'))
from sae_data import MesuresRepository
from sae_data.connexion import creer_factory
from sae_data.validation import valider_config
from demo import generer_evenement


def charger(nom):
    """Charge une configuration versionnée depuis un fichier JSON."""
    config = json.loads((ROOT / 'scenarios' / f'scenario_{nom}.json').read_text(encoding='utf8'))
    valider_config(config)
    return config


def executer(config, priorite, limite=120):
    """Exécute un essai isolé ; mesure le départ au début du pas d'apparition."""
    name = '_moteur_' + uuid4().hex
    spec = importlib.util.spec_from_file_location(name, ROOT / 'sae302_Jamais2sans3/simulation.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        assert config['step_s'] == module.DT
        assert config['initial_lights'] == module.ControleFeux(priorite).etats()
        routes = {k: {'points': [list(p) for p in r.points], 'stop_index': r.arret_point, 'light': r.feu}
                  for k, r in module.TRAJETS.items()}
        assert config['geometry']['routes'] == routes, 'Geometrie du moteur modifiee'
        assert config['lights']['phases'] == [list(p) for p in module.ControleFeux.CYCLE]
        rows = []
        for a in config['arrivals']:
            assert a['route'] in module.TRAJETS and a['initial_s_px'] == 0
            assert 0 < a['speed_px_s'] <= 100
            assert abs(a['scheduled_s']/module.DT-round(a['scheduled_s']/module.DT)) < 1e-7
            rows.append((a['scheduled_s'], a['vehicle_id'], a['route'], '#ffffff' if a['vehicle_id']=='A1' else '#2e9de6', a['speed_px_s'], a['vehicle_id']=='A1'))
        module.SCENARIO = tuple(sorted(rows, key=lambda r:r[0]))
        sim = module.Simulation(priorite)
        depart = None
        for _ in range(round(limite/module.DT)):
            avant = round(sim.t, 6)
            sim.avancer()
            if depart is None and any(v.ambulance for v in sim.vehicules):
                depart = avant
            if sim.ambulance_terminee is not None:
                arrivee = round(sim.ambulance_terminee, 6)
                return dict(status='TERMINE', departure_s=depart, arrival_s=arrivee,
                            duration_s=round(arrivee-depart,6), end_s=arrivee)
        return dict(status='INTERROMPU', departure_s=depart, arrival_s=None,
                    duration_s=None, end_s=round(sim.t,6))
    finally:
        sys.modules.pop(name, None)


def comparer(config, repo=None):
    """Compare deux essais identiques et, si demandé, sauvegarde puis relit leur gain."""
    cid = str(uuid4())
    result = {'comparison_id':cid, 'config':config, 'essais':{}}
    if repo:
        repo.creer_comparaison(config, cid, data_origin='SIMULATION')
    for mode in ('SANS','AVEC'):
        trial = executer(config, mode=='AVEC')
        trial['trial_id'] = str(uuid4())
        result['essais'][mode] = trial
        if repo:
            meta = repo.ouvrir_essai(cid, mode, trial['trial_id'])
            events = [('trial_started',0)]
            if trial['departure_s'] is not None:
                events.append(('priority_departed',trial['departure_s']))
            if trial['status']=='TERMINE':
                events.append(('priority_arrived',trial['arrival_s']))
            else:
                events.append(('trial_interrupted',trial['end_s']))
            for kind,t in events:
                event = generer_evenement(meta, kind, t)
                if kind=='trial_interrupted': event['reason']='timeout'
                repo.traiter_evenement(event)
    sans,avec = (result['essais'][m]['duration_s'] for m in ('SANS','AVEC'))
    result['gain_s'] = None if sans is None or avec is None else round(sans-avec,6)
    if repo:
        lu = repo.lire_comparaison(cid)
        assert (None if lu['gain_s'] is None else float(lu['gain_s'])) == result['gain_s']
    result['moteur_sha256'] = hashlib.sha256((ROOT/'sae302_Jamais2sans3/simulation.py').read_bytes()).hexdigest()
    return result


def main():
    """Produit des mesures JSON ; --config active explicitement MariaDB."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', help='Chemin absolu vers un INI prive, hors du depot')
    parser.add_argument('--scenario', choices=['normal','dense','urgence','tous'],default='tous')
    args=parser.parse_args()
    repo=MesuresRepository(creer_factory(args.config)) if args.config else None
    noms=['normal','dense','urgence'] if args.scenario=='tous' else [args.scenario]
    print(json.dumps([comparer(charger(n),repo) for n in noms],ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
