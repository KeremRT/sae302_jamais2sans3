"""Trois fonctions pour connecter, sauvegarder et lire les résultats MariaDB."""
import configparser
import hashlib
import json
from uuid import uuid4
import pymysql


def connecter(fichier_config):
    """Ouvre MariaDB avec les identifiants d'un fichier privé."""
    config = configparser.ConfigParser(interpolation=None)
    if not config.read(fichier_config, encoding='utf-8'):
        raise ValueError('Fichier de configuration introuvable.')
    db = config['database']
    return pymysql.connect(host=db['host'], port=int(db['port']),
                           user=db['user'], password=db['password'],
                           database=db['database'], charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor, autocommit=False)


def enregistrer(connexion, resultat, origine='SIMULATION'):
    """Sauvegarde le scénario et ses deux essais dans une seule transaction."""
    if origine not in ('SIMULATION', 'EXEMPLE'):
        raise ValueError('Origine inconnue.')
    scenario = resultat['scenario']
    texte = json.dumps(scenario, ensure_ascii=False, sort_keys=True)
    # L'empreinte sert à reconnaître une modification du scénario.
    empreinte = hashlib.sha256(texte.encode('utf-8')).hexdigest()
    identifiant = str(uuid4())  # Un identifiant différent pour chaque comparaison.
    try:
        connexion.begin()
        with connexion.cursor() as curseur:
            curseur.execute('SELECT config_json FROM scenarios WHERE scenario_id=%s AND scenario_version=%s',
                            (scenario['code'], scenario['version']))
            ancien = curseur.fetchone()
            if ancien is None:
                curseur.execute('INSERT INTO scenarios VALUES (%s,%s,%s,%s)',
                                (scenario['code'], scenario['version'], texte, empreinte))
            elif ancien['config_json'] != texte:
                raise ValueError('Scénario modifié : augmenter sa version dans le JSON.')
            curseur.execute('INSERT INTO comparisons (comparison_id,scenario_id,scenario_version,config_json,config_sha256,data_origin) VALUES (%s,%s,%s,%s,%s,%s)',
                            (identifiant, scenario['code'], scenario['version'], texte, empreinte, origine))
            for mode in ('SANS', 'AVEC'):
                essai = resultat[mode]
                termine = essai['etat'] == 'TERMINE'
                if termine and (essai['depart'] is None or essai['arrivee'] is None or
                                round(essai['arrivee']-essai['depart'], 6) != essai['duree']):
                    raise ValueError('Durée incohérente avec le départ et l’arrivée.')
                curseur.execute('INSERT INTO trials (trial_id,comparison_id,mode,status,departure_s,arrival_s,duration_s,last_sim_time_s,interruption_reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                (str(uuid4()), identifiant, mode, essai['etat'], essai['depart'],
                                 essai['arrivee'], essai['duree'],
                                 essai['arrivee'] if termine else scenario['duree_max'],
                                 None if termine else 'timeout'))
        connexion.commit()  # Les deux essais sont enregistrés ensemble.
        return identifiant
    except Exception:
        connexion.rollback()  # En cas d'erreur, aucune moitié de comparaison.
        raise


def lire_resultats(connexion, identifiant):
    """Retrouve les deux essais à partir de l'identifiant de comparaison."""
    with connexion.cursor() as curseur:
        curseur.execute('SELECT mode,status,duration_s FROM trials WHERE comparison_id=%s ORDER BY mode',
                        (identifiant,))
        return curseur.fetchall()
