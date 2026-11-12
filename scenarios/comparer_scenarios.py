"""Charge un scénario et compare les deux modes avec le moteur de Kerem."""
import argparse
import json
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOSSIER / 'sae302_Jamais2sans3'))
sys.path.insert(0, str(DOSSIER / 'sql'))
import simulation


def charger_scenario(nom):
    """Lit les véhicules et les paramètres dans le fichier JSON."""
    fichier = DOSSIER / 'scenarios' / f'scenario_{nom}.json'
    with open(fichier, encoding='utf-8') as fichier_json:
        return json.load(fichier_json)


def faire_essai(scenario, priorite):
    """Lance un essai et renvoie le départ, l'arrivée et la durée simulée."""
    if not 0 < scenario['duree_max'] <= 120:
        raise ValueError('La durée maximale doit être comprise entre 0 et 120 secondes.')
    calendrier = []
    for voiture in scenario['vehicules']:
        if voiture['trajet'] not in simulation.TRAJETS or voiture['vitesse'] <= 0:
            raise ValueError('Trajet inconnu ou vitesse incorrecte.')
        if not 0 <= voiture['arrivee'] <= 120:
            raise ValueError('Horaire d’arrivée hors de la durée du scénario.')
        couleur = '#ffffff' if voiture['ambulance'] else '#2e9de6'
        calendrier.append((voiture['arrivee'], voiture['id'], voiture['trajet'],
                           couleur, voiture['vitesse'], voiture['ambulance']))
    if sum(v['ambulance'] for v in scenario['vehicules']) != 1:
        raise ValueError('Il faut exactement une ambulance.')

    # Le moteur lit une constante SCENARIO. On la remplace en mémoire seulement.
    ancien_scenario = simulation.SCENARIO
    simulation.SCENARIO = tuple(sorted(calendrier, key=lambda v: v[0]))
    try:
        essai = simulation.Simulation(priorite)
        if essai.controle.etats() != scenario['feux_depart']:
            raise ValueError('Les feux de départ ne correspondent pas au moteur.')
        depart = None
        for _ in range(round(scenario['duree_max'] / simulation.DT)):
            temps_avant = round(essai.t, 6)
            essai.avancer()
            if depart is None and any(v.ambulance for v in essai.vehicules):
                # Le véhicule parcourt déjà un pas au moment de son apparition.
                depart = temps_avant
            if essai.ambulance_terminee is not None:
                arrivee = round(essai.ambulance_terminee, 6)
                return {'etat': 'TERMINE', 'depart': depart, 'arrivee': arrivee,
                        'duree': round(arrivee - depart, 6)}
        return {'etat': 'INTERROMPU', 'depart': depart, 'arrivee': None, 'duree': None}
    finally:
        simulation.SCENARIO = ancien_scenario


def calculer_gain(sans, avec):
    """Calcule sans moins avec, ou None si un des essais est incomplet."""
    if sans['duree'] is None or avec['duree'] is None:
        return None
    return round(sans['duree'] - avec['duree'], 6)


def comparer(scenario):
    """Exécute le même calendrier deux fois ; seule la priorité change."""
    sans = faire_essai(scenario, False)
    avec = faire_essai(scenario, True)
    return {'scenario': scenario, 'SANS': sans, 'AVEC': avec,
            'gain': calculer_gain(sans, avec)}


def main():
    """Affiche les résultats et enregistre dans MariaDB si --config est fourni."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['normal', 'dense', 'urgence', 'tous'], default='tous')
    parser.add_argument('--config', help='Fichier INI privé pour MariaDB')
    args = parser.parse_args()
    noms = ['normal', 'dense', 'urgence'] if args.scenario == 'tous' else [args.scenario]
    resultats = []
    for nom in noms:
        resultat = comparer(charger_scenario(nom))
        if args.config:
            from base_donnees import connecter, enregistrer, lire_resultats
            connexion = connecter(args.config)
            try:
                identifiant = enregistrer(connexion, resultat)
                resultat['id_comparaison'] = identifiant
                # Vérifier que les durées sauvegardées correspondent aux mesures.
                lignes = lire_resultats(connexion, identifiant)
                for ligne in lignes:
                    duree = ligne['duration_s']
                    assert (float(duree) if duree is not None else None) == resultat[ligne['mode']]['duree']
            finally:
                connexion.close()
        resultats.append(resultat)
    print(json.dumps(resultats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
