"""Serveur TCP de la SAE 3.02 .

Une seule connexion active à la fois pour la démonstration.
Kerem : simulation Qt / Windows. Huy-Ming : stockage MariaDB.
Aucune connexion à des feux réels.
"""
import argparse
import json
import logging
import socketserver
from uuid import uuid4

from sae_data import MesuresRepository
from sae_data.connexion import creer_factory
from sae_data.protocol import LecteurJSONL
from sae_data.repository import ErreurStockage
from sae_data.validation import DonneesInvalides, temps_valide
from scenarios_loader import charger_scenario
from priorite_simple import PrioriteReseau

LOG = logging.getLogger('SAE302')
PHASES = {'NS_GREEN', 'NS_AMBER', 'EO_GREEN', 'EO_AMBER',
          'SO_GREEN', 'SO_AMBER', 'ALL_RED'}
EVENTS = {'trial_started', 'priority_departed', 'priority_arrived', 'trial_interrupted'}


class Gestionnaire(socketserver.StreamRequestHandler):
    """Gère les messages d'un client Windows pendant un essai."""

    def setup(self):
        """Initialise les informations de la connexion cliente au serveur."""
        super().setup()
        self.comparison_id = None
        self.trials = {}
        self.config = None
        self.current = None
        self.status = 'PRET'
        self.last_time = 0.0
        self.last_phase = 'ALL_RED'
        self.priority = None
        # Lecteur de Huy-Ming : valide les lignes JSON reçues sur TCP.
        self.reader = LecteurJSONL()
        LOG.info('Client connecté : %s', self.client_address)

    def send(self, msg):
        """Envoie une réponse JSON terminée par un saut de ligne au client."""
        raw = (json.dumps(msg, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
        self.wfile.write(raw)
        self.wfile.flush()

    def repo(self):
        """Renvoie le module de stockage partagé par le serveur."""
        return self.server.repo

    def current_required(self, msg):
        """Vérifie que le message concerne l’essai actif."""
        if self.current is None or msg.get('trial_id') != self.current['trial_id']:
            raise DonneesInvalides('trial_id absent ou différent de l essai actif.')

    def create(self, msg):
        """Crée une comparaison et ses deux essais à partir du scénario demandé."""
        if self.comparison_id is not None:
            raise DonneesInvalides('Une comparaison existe déjà sur cette connexion.')
        sid = msg.get('scenario_id')
        if sid not in ('S01', 'S02', 'S03'):
            raise DonneesInvalides('Scénario inconnu.')
        # Le serveur conserve une configuration de référence pour la paire SANS/AVEC.
        self.config = charger_scenario(sid)
        # Huy-Ming utilise des UUID pour relier comparaisons, essais et événements.
        # str(uuid4()) génère automatiquement un identifiant unique.
        self.comparison_id = str(uuid4())
        self.repo().creer_comparaison(self.config, self.comparison_id, 'SIMULATION')
        for mode in ('SANS','AVEC'):
            tid = str(uuid4())
            self.trials[mode] = self.repo().ouvrir_essai(self.comparison_id, mode, tid)
        self.send({'type': 'comparison_ready', 'comparison_id': self.comparison_id,
                   'trials': {k:v['trial_id'] for k,v in self.trials.items()},
                   'scenario_id': sid, 'scenario_version': self.config['scenario_version']})

    def choose(self, msg):
        """Sélectionne un essai disponible et transmet sa configuration au client."""
        mode = msg.get('mode')
        if mode not in self.trials:
            raise DonneesInvalides('Créer la comparaison puis choisir SANS ou AVEC.')
        if self.current is not None and self.status not in ('TERMINE', 'INTERROMPU'):
            raise DonneesInvalides('Terminer ou interrompre l essai actif.')
        current = self.trials[mode]
        res = self.repo().lire_comparaison(self.comparison_id)
        if res['essais'][mode]['status'] != 'PRET':
            raise DonneesInvalides('Cet essai a déjà été lancé.')
        self.current = current
        self.status = 'PRET'
        self.last_time = 0.0
        self.last_phase = 'NS_GREEN'
        self.priority = PrioriteReseau(
            amber_s=float(self.config['priority']['amber_s']),
            all_red_s=float(self.config['priority']['all_red_s']))
        self.send({'type': 'start_trial', **current, 'config': self.config})

    def event(self, msg):
        """Sauvegarde un événement puis confirme sa prise en compte au client."""
        self.current_required(msg)
        ack = self.repo().traiter_evenement(msg)
        self.status = ack['status']
        self.send({'type': 'ack', **ack})

    def traffic(self, msg):
        """Valide l’état de circulation reçu et renvoie un éventuel ordre de feu."""
        self.current_required(msg)
        if self.status != 'EN_COURS':
            raise DonneesInvalides('Essai non démarré.')
        t = float(temps_valide(msg.get('sim_time_s')))
        phase = msg.get('phase')
        libre = msg.get('crossing_clear')
        if t < self.last_time or phase not in PHASES or type(libre) is not bool:
            raise DonneesInvalides('État des feux ou temps invalide.')
        self.last_time = t
        self.last_phase = phase
        cmd = self.priority.point(t, phase, libre) if self.current['mode'] == 'AVEC' else None
        self.send(cmd or {'type': 'ok', 'sim_time_s': t})

    def request_priority(self, msg):
        """Traite la demande de priorité d’un essai AVEC en cours."""
        self.current_required(msg)
        if self.status != 'EN_COURS' or self.current['mode'] != 'AVEC':
            raise DonneesInvalides('Priorité impossible hors essai AVEC.')
        t = float(temps_valide(msg.get('sim_time_s')))
        if t < self.last_time:
            raise DonneesInvalides('Temps simulé en arrière.')
        self.last_time = t
        self.send(self.priority.demander(t, self.last_phase))

    def priority_clear(self, msg):
        """Signale la sortie de l’ambulance et déclenche le retour au cycle normal."""
        self.current_required(msg)
        if self.status != 'EN_COURS' or self.current['mode'] != 'AVEC':
            raise DonneesInvalides('Sortie de priorité impossible.')
        t = float(temps_valide(msg.get('sim_time_s')))
        if t < self.last_time:
            raise DonneesInvalides('Temps simulé en arrière.')
        self.last_time = t
        self.send(self.priority.degagee(t))

    def results(self):
        """Relit les résultats stockés et les transmet au client."""
        if not self.comparison_id:
            raise DonneesInvalides('Aucune comparaison.')
        result = self.repo().lire_comparaison(self.comparison_id)
        modes = {}
        for mode in ('SANS','AVEC'):
            r = result['essais'].get(mode)
            modes[mode] = None if r is None else {
                'status': r['status'], 'trial_id': r['trial_id'],
                'duration_s': float(r['duration_s']) if r['duration_s'] is not None else None}
        self.send({'type': 'comparison_result', 'comparison_id': self.comparison_id,
                   'scenario_id': result['scenario_id'], 'SANS': modes['SANS'],
                   'AVEC': modes['AVEC'], 'comparable': result['comparable'],
                   'gain_s': float(result['gain_s']) if result['gain_s'] is not None else None})

    def dispatch(self, msg):
        """Oriente un message JSON vers le traitement correspondant à son type."""
        kind = msg.get('type')
        if kind == 'ping':
            self.send({'type': 'pong'})
        elif kind == 'create_comparison':
            self.create(msg)
        elif kind == 'choose_trial':
            self.choose(msg)
        elif kind in EVENTS:
            self.event(msg)
        elif kind == 'traffic_state':
            self.traffic(msg)
        elif kind == 'priority_request':
            self.request_priority(msg)
        elif kind == 'priority_clear':
            self.priority_clear(msg)
        elif kind == 'get_results':
            self.results()
        else:
            raise DonneesInvalides('Message inconnu.')

    def handle(self):
        """Traite les messages TCP et signale une interruption lors d’une déconnexion."""
        try:
            while True:
                # TCP : on lit une ligne JSON terminée par \n.
                ligne = self.rfile.readline(16385)
                if not ligne:
                    self.reader.finish()
                    break
                for msg in self.reader.feed(ligne):
                    try:
                        self.dispatch(msg)
                    except (DonneesInvalides, ValueError, KeyError, ErreurStockage) as exc:
                        LOG.warning('Message refusé : %s', exc)
                        self.send({'type': 'error', 'message': str(exc)})
        except (OSError, DonneesInvalides) as exc:
            LOG.warning('Connexion interrompue : %s', exc)
        finally:
            if self.current and self.status in ('PRET','EN_COURS'):
                try:
                    msg = dict(self.current, type='trial_interrupted', protocol_version=1,
                               event_id=str(uuid4()), sim_time_s=self.last_time,
                               reason='connection_lost')
                    self.repo().traiter_evenement(msg)
                    LOG.warning('Essai interrompu suite à la déconnexion')
                except Exception:
                    LOG.exception('Impossible de signaler interruption dans MariaDB')


class Serveur(socketserver.TCPServer):
    """Version BUT2 : une connexion cliente à la fois, sans threads côté serveur."""
    allow_reuse_address = True


def main():
    """Configure MariaDB puis démarre le serveur TCP."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--config', default='config.ini')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    repo = MesuresRepository(creer_factory(args.config))
    with Serveur((args.host, args.port), Gestionnaire) as server:
        server.repo = repo
        LOG.info('Serveur Youssef démarré sur %s:%d (modèle virtuel seulement)', args.host, args.port)
        server.serve_forever()

if __name__ == '__main__':
    main()
