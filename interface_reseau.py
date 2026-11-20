"""Interface graphique réseau de la SAE 3.02 (Windows).

Elle réutilise la fenêtre de Kerem (main.py, NON modifié).
La simulation tourne dans un QThread pour garder les boutons réactifs.
Ce thread appelle le client TCP, puis transmet les images à la fenêtre Qt.
"""

import argparse
import copy
import os
import sys
import threading
import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from main import Fenetre
from client_reseau import executer_comparaison_reseau
from simulation import Simulation


class TravailReseau(QThread):
    """Exécute le client TCP sans bloquer la fenêtre graphique."""

    # Les signaux transmettent les informations du thread vers la fenêtre.
    image = Signal(object, str)
    termine = Signal(object)
    erreur = Signal(str)

    def __init__(self, scenario_id, host, port):
        """Prépare le scénario, l’adresse du serveur et le signal d’arrêt."""
        super().__init__()
        self.scenario_id = scenario_id
        self.host = host
        self.port = port
        self.arret = threading.Event()

    def demander_arret(self):
        # La boucle de simulation vérifie régulièrement cette demande.
        """Signale au travail réseau qu’il doit interrompre l’essai."""
        self.arret.set()

    def run(self):
        """Méthode exécutée par Qt dans un thread distinct."""
        try:
            def afficher_image(simulation, mode):
                # Qt ne doit pas lire le moteur pendant qu'il est modifié.
                # On lui envoie donc une copie de l'état à afficher.
                """Transmet une copie de la simulation à la fenêtre et rythme l’affichage."""
                self.image.emit(copy.deepcopy(simulation), mode)
                time.sleep(0.012)  # Laisse le temps à Qt de dessiner.

            resultat = executer_comparaison_reseau(
                self.scenario_id,
                self.host,
                self.port,
                frame_callback=afficher_image,
                stop_callback=self.arret.is_set,
            )
            self.termine.emit(resultat)
        except Exception as erreur:
            self.erreur.emit(str(erreur))


class FenetreReseau(Fenetre):
    """Fenêtre de Kerem dont les boutons lancent la version réseau."""

    def __init__(self, host, port):
        """Adapte les boutons de la fenêtre au fonctionnement réseau."""
        self.host = host
        self.port = port
        self.worker = None
        super().__init__()
        self.setWindowTitle('SAÉ 3.02 — Jamais2sans3 | Mode réseau TCP')

        # On utilise les boutons existants : aucune modification de main.py.
        self.demarrer.clicked.disconnect()
        self.demarrer.clicked.connect(self.lancer_reseau)
        self.comparer.clicked.disconnect()
        self.comparer.clicked.connect(self.lancer_reseau)
        self.pause.clicked.disconnect()
        self.pause.clicked.connect(self.arreter_reseau)
        self.reset.clicked.disconnect()
        self.reset.clicked.connect(self.recommencer)

        # Le mode SANS puis AVEC est choisi automatiquement par le client.
        self.priorite.setEnabled(False)
        self.demarrer.setText('▶ Démarrer réseau')
        self.comparer.setText('Comparer via serveur TCP')
        self.pause.setText('⏹ Arrêter essai')
        for etiquette in self.findChildren(QLabel):
            if 'Contrôle local simulé' in etiquette.text():
                etiquette.setText(
                    f'Serveur TCP : {host}:{port}\nDeux essais SANS puis AVEC'
                )
        self.rafraichir()

    def lancer_reseau(self):
        """Démarre une comparaison complète sur le scénario sélectionné."""
        if self.worker is not None and self.worker.isRunning():
            return  # Empêche de lancer deux simulations simultanément.
        self.recommencer()
        scenario_id = self.choix_scenario.currentData()

        self.worker = TravailReseau(scenario_id, self.host, self.port)
        self.worker.image.connect(self.nouvelle_image)
        self.worker.termine.connect(self.comparaison_terminee)
        self.worker.erreur.connect(self.erreur_reseau)

        self.en_cours = True
        self.worker.start()
        self.rafraichir()
        self.demarrer.setEnabled(False)
        self.comparer.setEnabled(False)

    def nouvelle_image(self, simulation, mode):
        """Affiche l'image reçue du thread réseau."""
        self.sim = simulation
        self.priorite.blockSignals(True)
        self.priorite.setChecked(mode == 'AVEC')
        self.priorite.blockSignals(False)
        self.rafraichir()
        self.comparer.setEnabled(False)

    def comparaison_terminee(self, resultat):
        """Affiche les durées calculées et enregistrées sur Debian."""
        self.en_cours = False
        if resultat.get('comparable'):
            self.resultats = (
                resultat['SANS']['duration_s'],
                resultat['AVEC']['duration_s'],
                resultat['gain_s'],
            )
        else:
            self.resultats = None
        self.sim.ajouter_evenement('Résultats TCP reçus depuis MariaDB')
        self.rafraichir()
        self.comparer.setEnabled(True)
        self.demarrer.setEnabled(True)

    def erreur_reseau(self, message):
        """Affiche une erreur si le serveur est arrêté ou si un essai échoue."""
        self.en_cours = False
        self.sim.ajouter_evenement('Erreur TCP : ' + message)
        self.rafraichir()
        self.comparer.setEnabled(True)
        self.demarrer.setEnabled(True)
        QMessageBox.warning(self, 'SAE 3.02 — Problème réseau', message)

    def arreter_reseau(self):
        """Demande l'interruption au prochain passage dans la boucle."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.demander_arret()
            self.sim.ajouter_evenement('Arrêt demandé au serveur')
            self.rafraichir()

    def recommencer(self):
        """Réinitialise l'affichage si aucun essai n'est encore actif."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.demander_arret()
            return
        self.en_cours = False
        self.timer.stop()
        self.sim = Simulation(priorite=True, scenario=self.scenario_config)
        self.resultats = None
        self.rafraichir()

    def closeEvent(self, event):
        # Ne pas détruire le thread pendant une requête TCP en cours.
        """Demande l’arrêt du travail réseau avant de fermer la fenêtre."""
        if self.worker is not None and self.worker.isRunning():
            self.worker.demander_arret()
            if not self.worker.wait(2000):
                event.ignore()
                return
        super().closeEvent(event)


def main():
    """Lit l’adresse du serveur et ouvre la fenêtre de simulation réseau."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.environ.get('SAE_SERVER_IP', '192.168.56.101'))
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    app = QApplication(sys.argv[:1])
    fenetre = FenetreReseau(args.host, args.port)
    fenetre.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
