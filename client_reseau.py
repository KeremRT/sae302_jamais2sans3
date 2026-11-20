"""Client TCP de la simulation du carrefour (Windows).

Ce fichier relie le moteur de Kerem au serveur de priorité sur Debian.
Les deux essais SANS / AVEC sont toujours réalisés sur le même scénario.
Les événements et les mesures sont enregistrés côté serveur par le module SQL.
"""

import argparse
import json
import os
import socket
from uuid import uuid4

from simulation import ControleFeux, Simulation, DT
from scenarios_loader import charger_scenario


def phase_des_feux(etats):
    """Traduit les cinq feux du dessin en une phase comprise par Debian."""
    if etats['F2'] == 'vert' and etats['F4'] == 'vert':
        return 'EO_GREEN'
    if etats['F1'] == 'vert' and etats['F3'] == 'vert':
        return 'NS_GREEN'
    if etats['F5'] == 'vert':
        return 'SO_GREEN'
    if etats['F2'] == 'orange' and etats['F4'] == 'orange':
        return 'EO_AMBER'
    if etats['F1'] == 'orange' and etats['F3'] == 'orange':
        return 'NS_AMBER'
    if etats['F5'] == 'orange':
        return 'SO_AMBER'
    return 'ALL_RED'


class ControleExterne(ControleFeux):
    """Applique les ordres de feux reçus de Debian, sans calculer la priorité."""

    def __init__(self):
        """Initialise le contrôleur en attente des commandes du serveur."""
        super().__init__(priorite=True)
        self.remote_phase = None

    def debut_priorite(self):
        """Déclenche une demande de priorité si aucune demande n’est en cours."""
        if not self.deja_demande:
            self.deja_demande = True
            self.evenement = 'Demande de priorité transmise au serveur Debian'

    def etats(self):
        """Renvoie la couleur de chacun des cinq feux."""
        if self.remote_phase is None:
            return super().etats()

        # Un axe correspond à un ou plusieurs feux du dessin de Kerem.
        axes = {'NS': ('F1', 'F3'), 'EO': ('F2', 'F4'), 'SO': ('F5',)}
        resultats = {f'F{i}': 'rouge' for i in range(1, 6)}
        if self.remote_phase != 'ALL_RED':
            axe, couleur = self.remote_phase.split('_')
            for feu in axes[axe]:
                resultats[feu] = {'GREEN': 'vert', 'AMBER': 'orange'}[couleur]
        return resultats

    def avancer(self, dt, ambulance_degagee=False):
        """Avance le cycle local seulement en l’absence de commande distante."""
        self.evenement = None
        # En l'absence d'ordre, conserver le cycle normal des feux de Kerem.
        if self.remote_phase is None:
            self.cycle_t = (self.cycle_t + dt) % self.DUREE_CYCLE

    def appliquer(self, phase):
        """Valide et applique une commande du serveur TCP."""
        if phase == 'NORMAL':
            self.remote_phase = None
            self.cycle_t = 0.0
            self.etape = 'normal'
        else:
            phases_valides = {
                'NS_GREEN', 'NS_AMBER', 'EO_GREEN', 'EO_AMBER',
                'SO_GREEN', 'SO_AMBER', 'ALL_RED',
            }
            if phase not in phases_valides:
                raise ValueError(f'Commande de feu non reconnue : {phase}')
            self.remote_phase = phase
            self.etape = 'priorite' if phase == 'EO_GREEN' else 'securite'
        self.evenement = f'Ordre du serveur : {phase}'

    @property
    def nom_phase(self):
        """Renvoie le libellé de la phase pour l’affichage."""
        if self.remote_phase:
            return 'Serveur : ' + self.remote_phase
        return 'Cycle normal (serveur en écoute)'


def zone_libre(sim):
    """Vérifie une zone APPROXIMATIVE du dessin (pas une sécurité réelle)."""
    for vehicule in sim.vehicules:
        x, y, _ = vehicule.position()
        if 450 <= x <= 650 and 290 <= y <= 450:
            return False
    return True


class Liaison:
    """Une connexion TCP ; chaque message est une ligne de texte JSON."""

    def __init__(self, host, port):
        """Ouvre la connexion TCP et prépare le lecteur de réponses JSON."""
        self.sock = socket.create_connection((host, port), timeout=15)
        self.sock.settimeout(15)
        self.fichier = self.sock.makefile('r', encoding='utf-8')

    def close(self):
        """Ferme le lecteur de messages et la connexion TCP."""
        try:
            self.fichier.close()
        finally:
            self.sock.close()

    def envoyer(self, message):
        # Le saut de ligne est important : il délimite le message sur TCP.
        """Envoie une ligne JSON et attend la réponse du serveur."""
        texte = json.dumps(message, ensure_ascii=False, allow_nan=False) + '\n'
        self.sock.sendall(texte.encode('utf-8'))

        reponse = self.fichier.readline()
        if not reponse:
            raise ConnectionError('Le serveur Debian a fermé la connexion.')

        donnees = json.loads(reponse)
        if donnees.get('type') == 'error':
            raise ValueError('Erreur du serveur : ' + donnees.get('message', 'inconnue'))
        return donnees


def appliquer_reponse(sim, reponse):
    """Applique un changement de feu uniquement si Debian en a envoyé un."""
    if reponse['type'] != 'feu_commande':
        return None
    phase = reponse['phase']
    sim.controle.appliquer(phase)
    sim.ajouter_evenement(f'Serveur Youssef : {phase}')
    return phase


def envoyer_evenement(liaison, infos_essai, nature, temps, **details):
    """Transmet un événement à MariaDB via Debian et attend son accusé de réception."""
    message = dict(
        infos_essai,
        type=nature,
        protocol_version=1,
        event_id=str(uuid4()),
        sim_time_s=round(temps, 6),
        **details,
    )
    reponse = liaison.envoyer(message)
    if reponse['type'] != 'ack':
        raise RuntimeError('Acquittement SQL attendu.')


def executer_essai(liaison, mode, scenario, commandes, frame_callback, stop_callback):
    """Réalise UN essai SANS ou AVEC et envoie les changements au serveur."""
    debut = liaison.envoyer({'type': 'choose_trial', 'mode': mode})
    if debut['type'] != 'start_trial':
        raise RuntimeError('Attendu : start_trial')

    infos = {cle: debut[cle] for cle in (
        'comparison_id', 'trial_id', 'scenario_id', 'scenario_version', 'mode'
    )}
    simulation = Simulation(priorite=(mode == 'AVEC'), scenario=scenario)
    if mode == 'AVEC':
        simulation.controle = ControleExterne()

    depart_envoye = False
    demande_envoyee = False
    sortie_envoyee = False
    envoyer_evenement(liaison, infos, 'trial_started', 0)

    # DT est le pas de temps du moteur de Kerem (0,05 s).
    # 2400 * 0,05 = 120 secondes simulées au maximum.
    for etape in range(2400):
        if stop_callback and stop_callback():
            envoyer_evenement(liaison, infos, 'trial_interrupted',
                              simulation.t, reason='user_stop')
            raise InterruptedError('Essai interrompu par l utilisateur.')

        simulation.avancer(DT)

        if simulation.ambulance_depart is not None and not depart_envoye:
            envoyer_evenement(liaison, infos, 'priority_departed',
                              simulation.ambulance_depart, vehicle_id='A1')
            depart_envoye = True

        # Le client observe les feux et le carrefour. La décision reste sur Debian.
        reponse = liaison.envoyer({
            'type': 'traffic_state',
            'trial_id': debut['trial_id'],
            'sim_time_s': simulation.t,
            'phase': phase_des_feux(simulation.controle.etats()),
            'crossing_clear': zone_libre(simulation),
        })
        commande = appliquer_reponse(simulation, reponse) if mode == 'AVEC' else None
        if commande:
            commandes.append((mode, simulation.t, commande))

        if mode == 'AVEC' and simulation.controle.deja_demande and not demande_envoyee:
            reponse = liaison.envoyer({
                'type': 'priority_request',
                'trial_id': debut['trial_id'],
                'sim_time_s': simulation.t,
            })
            commande = appliquer_reponse(simulation, reponse)
            if commande:
                commandes.append((mode, simulation.t, commande))
            demande_envoyee = True

        if mode == 'AVEC' and simulation.ambulance_degagee and not sortie_envoyee:
            reponse = liaison.envoyer({
                'type': 'priority_clear',
                'trial_id': debut['trial_id'],
                'sim_time_s': simulation.t,
            })
            commande = appliquer_reponse(simulation, reponse)
            if commande:
                commandes.append((mode, simulation.t, commande))
            sortie_envoyee = True

        # Qt reçoit une image sur quatre pour ne pas surcharger l'interface.
        if frame_callback and etape % 4 == 0:
            frame_callback(simulation, mode)

        if simulation.ambulance_terminee is not None:
            envoyer_evenement(liaison, infos, 'priority_arrived',
                              simulation.ambulance_terminee, vehicle_id='A1')
            if frame_callback:
                frame_callback(simulation, mode)
            break
    else:
        envoyer_evenement(liaison, infos, 'trial_interrupted', 120, reason='timeout')


def executer_comparaison_reseau(scenario_id, host='192.168.56.101', port=5000,
                                frame_callback=None, stop_callback=None):
    """Effectue SANS puis AVEC et retourne les résultats relus dans MariaDB."""
    scenario = charger_scenario(scenario_id)
    liaison = Liaison(host, port)
    commandes = []
    try:
        pret = liaison.envoyer({'type': 'create_comparison', 'scenario_id': scenario_id})
        if pret['type'] != 'comparison_ready':
            raise RuntimeError('Attendu : comparison_ready')

        for mode in ('SANS', 'AVEC'):
            executer_essai(liaison, mode, scenario, commandes,
                           frame_callback, stop_callback)

        resultat = liaison.envoyer({'type': 'get_results'})
        if resultat['type'] != 'comparison_result':
            raise RuntimeError('Comparaison non reçue.')
        resultat['commandes_feux'] = commandes
        return resultat
    finally:
        liaison.close()


def main():
    """Lit les options et lance les comparaisons via le serveur TCP."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.environ.get('SAE_SERVER_IP', '192.168.56.101'))
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--scenario', choices=['S01', 'S02', 'S03', 'tous'], default='S02')
    args = parser.parse_args()

    scenarios = ['S01', 'S02', 'S03'] if args.scenario == 'tous' else [args.scenario]
    for scenario_id in scenarios:
        resultat = executer_comparaison_reseau(scenario_id, args.host, args.port)
        sans = resultat['SANS']['duration_s']
        avec = resultat['AVEC']['duration_s']
        print(f'{scenario_id} : SANS={sans} s, AVEC={avec} s, GAIN={resultat["gain_s"]} s')
        print('Ordres de feux envoyés par Debian :', resultat['commandes_feux'])


if __name__ == '__main__':
    main()
