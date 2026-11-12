"""Persistance MariaDB, transactions atomiques et calcul des mesures.

Le serveur fournit les UUID. Chaque appel ouvre sa propre connexion. Les
acquittements reseau ne doivent etre envoyes qu'apres le retour sans erreur.
"""

from contextlib import contextmanager
from decimal import Decimal
import hashlib
import logging

from .validation import (DonneesInvalides, uuid4_valide, valider_evenement,
                         valider_config)

LOG = logging.getLogger(__name__)


class ErreurStockage(RuntimeError):
    """Erreur SQL ou connexion : aucune confirmation de sauvegarde possible."""


class MesuresRepository:
    def __init__(self, connection_factory):
        self._connect = connection_factory

    @contextmanager
    def _transaction(self):
        conn = None
        cursor = None
        try:
            conn = self._connect()
            conn.begin()
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception as exc:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    LOG.error('Rollback non confirme apres une erreur de connexion.')
            if isinstance(exc, DonneesInvalides):
                raise
            # Un COMMIT interrompu peut avoir abouti : rejouer le meme event_id.
            raise ErreurStockage('Sauvegarde/lecture non confirmee ; verifier la connexion.') from exc
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    LOG.warning('Fermeture du curseur non confirmee.')
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    LOG.warning('Fermeture de connexion non confirmee.')

    def creer_comparaison(self, config, comparison_id, data_origin='SIMULATION'):
        """Fige le scenario et cree la paire ; idempotent avec le meme contenu."""
        uuid4_valide(comparison_id, 'comparison_id')
        if data_origin not in ('SIMULATION', 'EXEMPLE'):
            raise DonneesInvalides('Origine de donnees inconnue.')
        serialized = valider_config(config)
        digest = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        sid, version = config['scenario_id'], config['scenario_version']
        with self._transaction() as cur:
            # Verrouille le scenario avant la comparaison, toujours dans cet ordre.
            cur.execute('SELECT config_json FROM scenarios WHERE scenario_id=%s '
                        'AND scenario_version=%s FOR UPDATE', (sid, version))
            scenario = cur.fetchone()
            if scenario:
                if scenario['config_json'] != serialized:
                    raise DonneesInvalides('Scenario modifie : augmenter scenario_version.')
            else:
                cur.execute('INSERT INTO scenarios '
                            '(scenario_id, scenario_version, config_json, config_sha256) '
                            'VALUES (%s,%s,%s,%s)', (sid, version, serialized, digest))
            cur.execute('SELECT * FROM comparisons WHERE comparison_id=%s FOR UPDATE',
                        (comparison_id,))
            old = cur.fetchone()
            if old:
                if old['config_json'] != serialized or old['data_origin'] != data_origin:
                    raise DonneesInvalides('comparison_id existe avec un contenu different.')
            else:
                cur.execute('INSERT INTO comparisons '
                            '(comparison_id,scenario_id,scenario_version,config_json,'
                            'config_sha256,data_origin) VALUES (%s,%s,%s,%s,%s,%s)',
                            (comparison_id, sid, version, serialized, digest, data_origin))
        return {'comparison_id': comparison_id, 'scenario_id': sid,
                'scenario_version': version, 'config_sha256': digest,
                'data_origin': data_origin}

    def ouvrir_essai(self, comparison_id, mode, trial_id):
        """Cree un essai PRET avant le message trial_started."""
        uuid4_valide(comparison_id, 'comparison_id')
        uuid4_valide(trial_id, 'trial_id')
        if mode not in ('SANS', 'AVEC'):
            raise DonneesInvalides('Mode inconnu.')
        with self._transaction() as cur:
            cur.execute('SELECT * FROM comparisons WHERE comparison_id=%s FOR UPDATE',
                        (comparison_id,))
            comp = cur.fetchone()
            if not comp:
                raise DonneesInvalides('Comparaison inconnue.')
            cur.execute('SELECT * FROM trials WHERE trial_id=%s FOR UPDATE', (trial_id,))
            trial = cur.fetchone()
            if trial:
                if trial['comparison_id'] != comparison_id or trial['mode'] != mode:
                    raise DonneesInvalides('trial_id deja attribue a un autre essai.')
            else:
                cur.execute('SELECT trial_id FROM trials WHERE comparison_id=%s AND mode=%s',
                            (comparison_id, mode))
                if cur.fetchone():
                    raise DonneesInvalides('Ce mode existe deja dans cette comparaison.')
                cur.execute('INSERT INTO trials (trial_id,comparison_id,mode,status) '
                            'VALUES (%s,%s,%s,%s)', (trial_id, comparison_id, mode, 'PRET'))
        return {'trial_id': trial_id, 'comparison_id': comparison_id,
                'scenario_id': comp['scenario_id'], 'scenario_version': comp['scenario_version'],
                'mode': mode}

    def traiter_evenement(self, message):
        """Valide, enregistre l'evenement et met a jour l'essai atomiquement."""
        event, t, payload = valider_evenement(message)
        trial_id = event['trial_id']
        duplicate = False
        with self._transaction() as cur:
            # Serialise les ecritures du meme essai, y compris les retransmissions.
            cur.execute('SELECT * FROM trials WHERE trial_id=%s FOR UPDATE', (trial_id,))
            trial = cur.fetchone()
            if not trial:
                raise DonneesInvalides('Essai inconnu ; ouvrir_essai est requis.')
            cur.execute('SELECT * FROM comparisons WHERE comparison_id=%s',
                        (trial['comparison_id'],))
            comp = cur.fetchone()
            expected = {'comparison_id': comp['comparison_id'],
                        'scenario_id': comp['scenario_id'],
                        'scenario_version': comp['scenario_version'], 'mode': trial['mode']}
            if any(event[k] != v for k, v in expected.items()):
                raise DonneesInvalides('Identifiants, scenario, version ou mode incoherents.')
            cur.execute('SELECT payload_json FROM events WHERE event_id=%s',
                        (event['event_id'],))
            old = cur.fetchone()
            if old:
                if old['payload_json'] != payload:
                    raise DonneesInvalides('event_id reutilise avec un contenu different.')
                duplicate = True
            else:
                self._appliquer_transition(trial, event, t)
                cur.execute('INSERT INTO events '
                            '(event_id,trial_id,event_type,sim_time_s,payload_json) '
                            'VALUES (%s,%s,%s,%s,%s)',
                            (event['event_id'], trial_id, event['type'], t, payload))
                cur.execute('UPDATE trials SET status=%s, departure_s=%s, arrival_s=%s, '
                            'duration_s=%s, last_sim_time_s=%s, interruption_reason=%s '
                            'WHERE trial_id=%s',
                            (trial['status'], trial['departure_s'], trial['arrival_s'],
                             trial['duration_s'], t, trial['interruption_reason'], trial_id))
        return {'event_id': event['event_id'], 'trial_id': trial_id,
                'duplicate': duplicate, 'status': trial['status']}

    @staticmethod
    def _appliquer_transition(trial, event, t):
        kind, status = event['type'], trial['status']
        if t < Decimal(str(trial['last_sim_time_s'])):
            raise DonneesInvalides('Temps simule anterieur au dernier evenement.')
        if status in ('TERMINE', 'INTERROMPU'):
            raise DonneesInvalides('Essai deja cloture ; creer un nouvel essai pour rejouer.')
        if kind == 'trial_started':
            if status != 'PRET':
                raise DonneesInvalides('Essai deja demarre.')
            trial['status'] = 'EN_COURS'
        elif kind == 'priority_departed':
            if status != 'EN_COURS' or trial['departure_s'] is not None:
                raise DonneesInvalides('Depart sans lancement ou depart deja recu.')
            trial['departure_s'] = t
        elif kind == 'priority_arrived':
            if status != 'EN_COURS' or trial['departure_s'] is None:
                raise DonneesInvalides('Arrivee sans depart.')
            departure = Decimal(str(trial['departure_s']))
            if t < departure:
                raise DonneesInvalides('Arrivee avant le depart.')
            trial['arrival_s'] = t
            trial['duration_s'] = t - departure
            trial['status'] = 'TERMINE'
        elif kind == 'trial_interrupted':
            # Une panne avant trial_started peut interrompre un essai PRET.
            trial['status'] = 'INTERROMPU'
            trial['interruption_reason'] = event['reason']

    def lire_comparaison(self, comparison_id):
        """Une lecture transactionnelle renvoie des Decimal, sans arrondi d'affichage."""
        uuid4_valide(comparison_id, 'comparison_id')
        with self._transaction() as cur:
            cur.execute('SELECT * FROM comparisons WHERE comparison_id=%s', (comparison_id,))
            comp = cur.fetchone()
            if not comp:
                raise DonneesInvalides('Comparaison inconnue.')
            cur.execute('SELECT * FROM trials WHERE comparison_id=%s', (comparison_id,))
            trials = cur.fetchall()
        by_mode = {t['mode']: t for t in trials}
        sans, avec = by_mode.get('SANS'), by_mode.get('AVEC')
        comparable = (sans is not None and avec is not None
                      and sans['status'] == 'TERMINE' and avec['status'] == 'TERMINE')
        gain = (Decimal(str(sans['duration_s'])) - Decimal(str(avec['duration_s']))
                if comparable else None)
        return {'comparison_id': comparison_id, 'scenario_id': comp['scenario_id'],
                'scenario_version': comp['scenario_version'], 'data_origin': comp['data_origin'],
                'config_sha256': comp['config_sha256'], 'essais': by_mode,
                'comparable': comparable, 'gain_s': gain}
