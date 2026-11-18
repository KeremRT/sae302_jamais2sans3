import argparse
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scenarios'))
from comparer_scenarios import charger_scenario, comparer
from base_donnees import connecter, enregistrer, lire_resultats


def tester(fichier):

    connexion = connecter(fichier)
    try:
        with connexion.cursor() as curseur:
            curseur.execute('SELECT DATABASE() AS nom')
            nom_base = curseur.fetchone()['nom']
            if 'test' not in nom_base and 'validation' not in nom_base:
                raise ValueError('Utiliser une base dont le nom contient test ou validation.')
        resultat = comparer(charger_scenario('normal'))

        resultat['SANS'], resultat['AVEC'] = resultat['AVEC'], resultat['SANS']
        identifiant = enregistrer(connexion, resultat, 'EXEMPLE')
        lignes = lire_resultats(connexion, identifiant)
        durees = {ligne['mode']: float(ligne['duration_s']) for ligne in lignes}
        assert durees['SANS'] - durees['AVEC'] < 0

        incomplet = copy.deepcopy(resultat)
        incomplet['AVEC'] = {'etat': 'INTERROMPU', 'depart': 2, 'arrivee': None, 'duree': None}
        identifiant = enregistrer(connexion, incomplet, 'EXEMPLE')
        lignes = lire_resultats(connexion, identifiant)
        assert next(l for l in lignes if l['mode'] == 'AVEC')['duration_s'] is None

        with connexion.cursor() as curseur:
            curseur.execute('SELECT COUNT(*) AS nombre FROM comparisons')
            avant = curseur.fetchone()['nombre']
        incorrect = copy.deepcopy(resultat)
        incorrect['AVEC']['duree'] = -10
        try:
            enregistrer(connexion, incorrect, 'EXEMPLE')
            raise AssertionError('Une durée incorrecte a été acceptée.')
        except ValueError:
            pass
        with connexion.cursor() as curseur:
            curseur.execute('SELECT COUNT(*) AS nombre FROM comparisons')
            assert curseur.fetchone()['nombre'] == avant
        print('OK : relecture, gain négatif, essai incomplet et rollback.')
    finally:
        connexion.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    tester(parser.parse_args().config)
