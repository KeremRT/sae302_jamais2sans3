"""Gestion des feux de la maquette (version BUT2, sans bibliothèque spéciale).

Le serveur n'utilise pas time.sleep() : il reçoit le temps SIMULÉ
et attend la confirmation de chaque changement de feu.
"""

from sae_data.validation import DonneesInvalides


class PrioriteReseau:
    """Décide des transitions de feux à partir du temps simulé reçu."""
    def __init__(self, amber_s=1.5, all_red_s=1.0):
        """Initialise les durées de transition et l’état normal du serveur."""
        self.orange_s = amber_s
        self.rouge_s = all_red_s
        self.etat = "NORMAL"
        self.debut = 0.0
        self.phase_attendue = None

    def commande(self, phase, temps):
        # Mémoriser l'ordre : le client devra confirmer le nouvel état.
        """Prépare un ordre de feu et mémorise la phase attendue en retour."""
        self.phase_attendue = phase
        return {"type": "feu_commande", "phase": phase,
                "sim_time_s": round(float(temps), 6), "raison": self.etat}

    def demander(self, temps, phase_actuelle):
        """Une ambulance arrive sur l'axe Ouest -> Est."""
        if self.etat != "NORMAL":
            raise DonneesInvalides("Une priorité est déjà en cours.")
        self.debut = temps
        if phase_actuelle == "EO_GREEN":
            self.etat = "PRIORITE"
            return self.commande("EO_GREEN", temps)
        if phase_actuelle.endswith(("_GREEN", "_AMBER")):
            self.etat = "ORANGE"
            axe = phase_actuelle.split("_")[0]
            return self.commande(axe + "_AMBER", temps)
        self.etat = "ROUGE"
        return self.commande("ALL_RED", temps)

    def point(self, temps, phase_actuelle, carrefour_libre):
        """Appelée régulièrement avec les infos reçues de Windows."""
        if self.etat == "NORMAL" or phase_actuelle != self.phase_attendue:
            return None

        duree = temps - self.debut
        if self.etat == "ORANGE" and duree >= self.orange_s - 1e-8:
            self.etat = "ROUGE"
            self.debut = temps
            return self.commande("ALL_RED", temps)

        if self.etat == "ROUGE" and duree >= self.rouge_s - 1e-8 and carrefour_libre:
            self.etat = "PRIORITE"
            self.debut = temps
            return self.commande("EO_GREEN", temps)

        if self.etat == "RETOUR_ORANGE" and duree >= self.orange_s - 1e-8:
            self.etat = "RETOUR_ROUGE"
            self.debut = temps
            return self.commande("ALL_RED", temps)

        if self.etat == "RETOUR_ROUGE" and duree >= self.rouge_s - 1e-8 and carrefour_libre:
            self.etat = "NORMAL"
            self.debut = temps
            return self.commande("NORMAL", temps)
        return None

    def degagee(self, temps):
        """L'ambulance est sortie de la zone prioritaire."""
        if self.etat != "PRIORITE" or self.phase_attendue != "EO_GREEN":
            raise DonneesInvalides("Ambulance sortie avant la confirmation du vert.")
        self.etat = "RETOUR_ORANGE"
        self.debut = temps
        return self.commande("EO_AMBER", temps)
