from decimal import Decimal
import hashlib
import logging

from .validation import (DonneesInvalides, uuid4_valide, valider_evenement,
                         valider_config)

LOG = logging.getLogger(__name__)


# Cette erreur sert à signaler un problème de stockage.
class ErreurStockage(RuntimeError):
    pass


# On regroupe ici les opérations qui lisent et enregistrent les essais.
class MesuresRepository:
    # On garde la fonction qui ouvre une connexion à la base.
    def __init__(self, connection_factory):
        self._connect = connection_factory

    # Si une opération échoue, on essaie d’annuler les écritures en attente.
    def _annuler(self, conn, erreur):
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                LOG.error('Rollback non confirme apres une erreur de connexion.')

        if isinstance(erreur, DonneesInvalides):
            raise erreur
        raise ErreurStockage(
            'Sauvegarde/lecture non confirmee ; verifier la connexion.'
        ) from erreur

    # On ferme le curseur puis la connexion s’ils ont été ouverts.
    def _fermer(self, conn, cur):
        if cur is not None:
            try:
                cur.close()
            except Exception:
                LOG.warning('Fermeture du curseur non confirmee.')
        if conn is not None:
            try:
                conn.close()
            except Exception:
                LOG.warning('Fermeture de connexion non confirmee.')

    # On enregistre les réglages communs aux essais avec et sans priorité.
    def creer_comparaison(self, config, comparison_id, data_origin='SIMULATION'):
        uuid4_valide(comparison_id, 'comparison_id')
        if data_origin not in ('SIMULATION', 'EXEMPLE'):
            raise DonneesInvalides('Origine de donnees inconnue.')
        configuration_json = valider_config(config)
        # On calcule une empreinte pour reconnaître les réglages du scénario.
        contenu = configuration_json.encode('utf-8')
        calcul = hashlib.sha256(contenu)
        empreinte = calcul.hexdigest()
        identifiant_scenario = config['scenario_id']
        version = config['scenario_version']
        conn = None
        cur = None
        try:
            conn = self._connect()
            conn.begin()
            cur = conn.cursor()
            requete = (
                'SELECT config_json FROM scenarios WHERE scenario_id=%s AND '
                'scenario_version=%s FOR UPDATE'
            )
            valeurs = (identifiant_scenario, version)
            cur.execute(requete, valeurs)
            # On vérifie que cette version du scénario correspond aux réglages déjà enregistrés.
            scenario = cur.fetchone()
            if scenario:
                if scenario['config_json'] != configuration_json:
                    raise DonneesInvalides('Scenario modifie : augmenter scenario_version.')
            else:
                requete = (
                    'INSERT INTO scenarios (scenario_id, scenario_version, config_json, '
                    'config_sha256) VALUES (%s,%s,%s,%s)'
                )
                valeurs = (
                    identifiant_scenario,
                    version,
                    configuration_json,
                    empreinte,
                )
                cur.execute(requete, valeurs)
            requete = (
                'SELECT * FROM comparisons WHERE comparison_id=%s FOR UPDATE'
            )
            valeurs = (comparison_id,)
            cur.execute(requete, valeurs)
            # On regarde si cet identifiant a déjà été enregistré.
            enregistrement_existant = cur.fetchone()
            if enregistrement_existant:
                if enregistrement_existant['config_json'] != configuration_json:
                    raise DonneesInvalides('comparison_id existe avec un contenu different.')
                if enregistrement_existant['data_origin'] != data_origin:
                    raise DonneesInvalides('comparison_id existe avec un contenu different.')
            else:
                requete = (
                    'INSERT INTO comparisons '
                    '(comparison_id,scenario_id,scenario_version,config_json,config_sha256,data_origin)'
                    ' VALUES (%s,%s,%s,%s,%s,%s)'
                )
                valeurs = (
                    comparison_id,
                    identifiant_scenario,
                    version,
                    configuration_json,
                    empreinte,
                    data_origin,
                )
                cur.execute(requete, valeurs)
            conn.commit()
        except Exception as erreur:
            self._annuler(conn, erreur)
        finally:
            self._fermer(conn, cur)
        return {'comparison_id': comparison_id, 'scenario_id': identifiant_scenario,
                'scenario_version': version, 'config_sha256': empreinte,
                'data_origin': data_origin}

    # On prépare un essai pour le mode choisi et on le marque PRET.
    def ouvrir_essai(self, comparison_id, mode, trial_id):
        uuid4_valide(comparison_id, 'comparison_id')
        uuid4_valide(trial_id, 'trial_id')
        if mode not in ('SANS', 'AVEC'):
            raise DonneesInvalides('Mode inconnu.')
        conn = None
        cur = None
        try:
            conn = self._connect()
            conn.begin()
            cur = conn.cursor()
            requete = (
                'SELECT * FROM comparisons WHERE comparison_id=%s FOR UPDATE'
            )
            valeurs = (comparison_id,)
            cur.execute(requete, valeurs)
            comp = cur.fetchone()
            if not comp:
                raise DonneesInvalides('Comparaison inconnue.')
            requete = (
                'SELECT * FROM trials WHERE trial_id=%s FOR UPDATE'
            )
            valeurs = (trial_id,)
            cur.execute(requete, valeurs)
            trial = cur.fetchone()
            if trial:
                if trial['comparison_id'] != comparison_id:
                    raise DonneesInvalides('trial_id deja attribue a un autre essai.')
                if trial['mode'] != mode:
                    raise DonneesInvalides('trial_id deja attribue a un autre essai.')
            else:
                requete = (
                    'SELECT trial_id FROM trials WHERE comparison_id=%s AND mode=%s'
                )
                valeurs = (comparison_id, mode)
                cur.execute(requete, valeurs)
                if cur.fetchone():
                    raise DonneesInvalides('Ce mode existe deja dans cette comparaison.')
                requete = (
                    'INSERT INTO trials (trial_id,comparison_id,mode,status) VALUES '
                    '(%s,%s,%s,%s)'
                )
                valeurs = (
                    trial_id,
                    comparison_id,
                    mode,
                    'PRET',
                )
                cur.execute(requete, valeurs)
            conn.commit()
        except Exception as erreur:
            self._annuler(conn, erreur)
        finally:
            self._fermer(conn, cur)
        return {'trial_id': trial_id, 'comparison_id': comparison_id,
                'scenario_id': comp['scenario_id'], 'scenario_version': comp['scenario_version'],
                'mode': mode}

    # On range l’événement dans le bon essai et on met à jour son état.
    def traiter_evenement(self, message):
        event, t, payload = valider_evenement(message)
        trial_id = event['trial_id']
        duplicate = False
        conn = None
        cur = None
        try:
            conn = self._connect()
            conn.begin()
            cur = conn.cursor()
            requete = (
                'SELECT * FROM trials WHERE trial_id=%s FOR UPDATE'
            )
            valeurs = (trial_id,)
            cur.execute(requete, valeurs)
            trial = cur.fetchone()
            if not trial:
                raise DonneesInvalides('Essai inconnu ; ouvrir_essai est requis.')
            requete = (
                'SELECT * FROM comparisons WHERE comparison_id=%s'
            )
            valeurs = (trial['comparison_id'],)
            cur.execute(requete, valeurs)
            comp = cur.fetchone()
            valeurs_attendues = {'comparison_id': comp['comparison_id'],
                        'scenario_id': comp['scenario_id'],
                        'scenario_version': comp['scenario_version'], 'mode': trial['mode']}
            # On vérifie que le message correspond au scénario et au mode de cet essai.
            for champ in valeurs_attendues:
                if event[champ] != valeurs_attendues[champ]:
                    raise DonneesInvalides(
                        'Identifiants, scenario, version ou mode incoherents.'
                    )
            requete = (
                'SELECT payload_json FROM events WHERE event_id=%s'
            )
            valeurs = (event['event_id'],)
            cur.execute(requete, valeurs)
            # On regarde si cet identifiant a déjà été enregistré.
            enregistrement_existant = cur.fetchone()
            if enregistrement_existant:
                if enregistrement_existant['payload_json'] != payload:
                    raise DonneesInvalides('event_id reutilise avec un contenu different.')
                duplicate = True
            else:
                # On prépare le nouvel état avant d’écrire le message et l’essai ensemble.
                self._appliquer_transition(trial, event, t)
                requete = (
                    'INSERT INTO events (event_id,trial_id,event_type,sim_time_s,payload_json) '
                    'VALUES (%s,%s,%s,%s,%s)'
                )
                valeurs = (
                    event['event_id'],
                    trial_id,
                    event['type'],
                    t,
                    payload,
                )
                cur.execute(requete, valeurs)
                requete = (
                    'UPDATE trials SET status=%s, departure_s=%s, arrival_s=%s, duration_s=%s, '
                    'last_sim_time_s=%s, interruption_reason=%s WHERE trial_id=%s'
                )
                valeurs = (
                    trial['status'],
                    trial['departure_s'],
                    trial['arrival_s'],
                    trial['duration_s'],
                    t,
                    trial['interruption_reason'],
                    trial_id,
                )
                cur.execute(requete, valeurs)
            conn.commit()
        except Exception as erreur:
            self._annuler(conn, erreur)
        finally:
            self._fermer(conn, cur)
        return {'event_id': event['event_id'], 'trial_id': trial_id,
                'duplicate': duplicate, 'status': trial['status']}

    # On vérifie l’ordre des événements et on calcule la durée à l’arrivée.
    @staticmethod
    def _appliquer_transition(trial, event, t):
        type_evenement = event['type']
        etat = trial['status']
        dernier_temps = Decimal(str(trial['last_sim_time_s']))
        if t < dernier_temps:
            raise DonneesInvalides('Temps simule anterieur au dernier evenement.')
        if etat in ('TERMINE', 'INTERROMPU'):
            raise DonneesInvalides('Essai deja cloture ; creer un nouvel essai pour rejouer.')
        if type_evenement == 'trial_started':
            if etat != 'PRET':
                raise DonneesInvalides('Essai deja demarre.')
            trial['status'] = 'EN_COURS'
        elif type_evenement == 'priority_departed':
            if etat != 'EN_COURS':
                raise DonneesInvalides('Depart sans lancement ou depart deja recu.')
            if trial['departure_s'] is not None:
                raise DonneesInvalides('Depart sans lancement ou depart deja recu.')
            trial['departure_s'] = t
        elif type_evenement == 'priority_arrived':
            if etat != 'EN_COURS':
                raise DonneesInvalides('Arrivee sans depart.')
            if trial['departure_s'] is None:
                raise DonneesInvalides('Arrivee sans depart.')
            departure = Decimal(str(trial['departure_s']))
            if t < departure:
                raise DonneesInvalides('Arrivee avant le depart.')
            trial['arrival_s'] = t
            trial['duration_s'] = t - departure
            trial['status'] = 'TERMINE'
        elif type_evenement == 'trial_interrupted':
            trial['status'] = 'INTERROMPU'
            trial['interruption_reason'] = event['reason']

    # On récupère les deux essais pour calculer le gain de temps.
    def lire_comparaison(self, comparison_id):
        uuid4_valide(comparison_id, 'comparison_id')
        conn = None
        cur = None
        try:
            conn = self._connect()
            conn.begin()
            cur = conn.cursor()
            requete = (
                'SELECT * FROM comparisons WHERE comparison_id=%s'
            )
            valeurs = (comparison_id,)
            cur.execute(requete, valeurs)
            comp = cur.fetchone()
            if not comp:
                raise DonneesInvalides('Comparaison inconnue.')
            requete = (
                'SELECT * FROM trials WHERE comparison_id=%s'
            )
            valeurs = (comparison_id,)
            cur.execute(requete, valeurs)
            trials = cur.fetchall()
            conn.commit()
        except Exception as erreur:
            self._annuler(conn, erreur)
        finally:
            self._fermer(conn, cur)
        # On range les essais par mode pour retrouver facilement les deux durées.
        essais_par_mode = {}
        for essai in trials:
            mode = essai['mode']
            essais_par_mode[mode] = essai

        sans = essais_par_mode.get('SANS')
        avec = essais_par_mode.get('AVEC')
        comparable = False
        gain = None
        # On calcule le gain seulement si les deux essais sont terminés.
        if sans is not None and avec is not None:
            if sans['status'] == 'TERMINE' and avec['status'] == 'TERMINE':
                comparable = True
                duree_sans = Decimal(str(sans['duration_s']))
                duree_avec = Decimal(str(avec['duration_s']))
                gain = duree_sans - duree_avec
        return {'comparison_id': comparison_id, 'scenario_id': comp['scenario_id'],
                'scenario_version': comp['scenario_version'], 'data_origin': comp['data_origin'],
                'config_sha256': comp['config_sha256'], 'essais': essais_par_mode,
                'comparable': comparable, 'gain_s': gain}
