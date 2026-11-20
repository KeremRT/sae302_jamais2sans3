"""Interface PySide6 pour la SAÉ 3.02 — Jamais2sans3.

Lancement (Windows) : .venv\\Scripts\\python.exe main.py
Le contrôle des feux est LOCAL dans cette première version : aucun échange
réseau ni commande d'équipements de voirie n'est réalisé.
"""
from __future__ import annotations

import sys
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSlider, QComboBox, QVBoxLayout, QWidget, QSizePolicy
)
from simulation import Simulation, DT, comparer
from scenarios_loader import charger_scenario

COULEURS = {
    'fond': '#eaf0e8', 'gazon': '#d4e5cc', 'route': '#34445a',
    'bordure': '#ffffff', 'navy': '#102b4a', 'gris': '#63768b',
    'rouge': '#eb4b57', 'vert': '#27b773', 'orange': '#f5b840',
}
FEUX_POSITION = {'F1': (614, 246), 'F2': (733, 308),
                 'F3': (615, 479), 'F4': (409, 304), 'F5': (356, 515)}
NOMS_FEUX = {'F1':'Nord', 'F2':'Est', 'F3':'Sud', 'F4':'Ouest', 'F5':'Sud-ouest'}


def couleur(valeur: str) -> QColor:
    """Convertit une valeur de couleur en objet QColor."""
    return QColor(valeur)


def tracer_polygone(pts):
    """Construit un chemin fermé à partir des points du polygone."""
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x,y) for x,y in pts]))
    path.closeSubpath()
    return path


def dessiner_fleche(p: QPainter, x: float, y: float, angle: float):
    """Dessine une flèche orientée à la position indiquée."""
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(QPen(QColor('#f7f8fb'), 4, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(QPointF(-19,0), QPointF(17,0))
    p.drawLine(QPointF(6,-10), QPointF(17,0))
    p.drawLine(QPointF(6,10), QPointF(17,0))
    p.restore()


class CarteCarrefour(QWidget):
    """Vue purement schématique : 5 branches, 5 feux, sans terre-plein central."""
    def __init__(self, fenetre):
        """Associe le dessin à sa fenêtre et configure sa taille."""
        super().__init__()
        self.fenetre = fenetre
        self.setMinimumSize(700, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        """Renvoie la taille souhaitée pour le dessin du carrefour."""
        return QSize(1040, 660)

    def paintEvent(self, event):
        """Redessine le carrefour et ses véhicules lors du rafraîchissement Qt."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor('#e3eaf0'))
        k = min(self.width()/1040.0, self.height()/660.0)
        p.translate((self.width()-1040*k)/2, (self.height()-660*k)/2)
        p.scale(k, k)
        p.setClipRect(QRectF(0,0,1040,660))
        self.fond(p)
        self.voirie(p)
        self.marquages(p)
        self.panneaux(p)
        if self.fenetre.voir_trajets.isChecked():
            self.trajets_pedagogiques(p)
        self.ambulance_trace(p)
        self.feux(p)
        self.vehicules(p)
        p.end()

    def fond(self, p):
        """Dessine les espaces verts et le décor du carrefour."""
        p.fillRect(QRectF(0,0,1040,660), couleur(COULEURS['fond']))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(couleur(COULEURS['gazon']))
        for r in (QRectF(45,50,260,175), QRectF(800,35,205,155),
                  QRectF(810,515,210,112), QRectF(40,490,180,124)):
            p.drawRoundedRect(r,15,15)
        p.setBrush(QColor('#bfd5b7'))
        for x,y,r in ((95,95,13),(220,170,19),(885,110,20),
                      (940,565,17),(123,565,16)):
            p.drawEllipse(QPointF(x,y),r,r)

    def voirie(self, p):
        # Les trois chaussées sont fusionnées pour supprimer les traits au milieu.
        # Ouest/Est, Nord/Sud et branche oblique de Fribourg (sud-ouest).
        """Dessine les chaussées des cinq branches."""
        h = tracer_polygone([(0,285),(405,285),(470,313),(630,313),
                            (1040,305),(1040,444),(615,444),
                            (465,448),(392,421),(0,421)])
        v = tracer_polygone([(455,0),(590,0),(590,660),(455,660)])
        d = tracer_polygone([(67,660),(386,422),(446,381),
                            (519,451),(450,517),(259,660)])
        tout = h.united(v).united(d)
        p.setBrush(couleur(COULEURS['route']))
        p.setPen(QPen(QColor('#ffffff'),4))
        p.drawPath(tout)

    def marquages(self, p):
        # Lignes longitudinales uniquement hors de la zone centrale.
        """Dessine les lignes d’arrêt et les flèches de circulation."""
        stylo = QPen(QColor('#e2eaf4'),2.5,Qt.PenStyle.DashLine)
        stylo.setDashPattern([11,8])
        p.setPen(stylo)
        for a,b in (((0,353),(354,367)),((790,373),(1040,373)),
                    ((522,0),(522,220)),((522,508),(522,660)),
                    ((136,660),(319,524))):
            p.drawLine(QPointF(*a),QPointF(*b))
        # Vraies lignes d'arrêt dans notre modèle (une par arrivée).
        p.setPen(QPen(QColor('#f9fafb'),6,Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.FlatCap))
        for a,b in (((399,372),(399,422)), ((718,312),(718,371)),
                    ((457,251),(519,251)),((524,489),(589,489)),
                    ((360,450),(416,500))):
            p.drawLine(QPointF(*a),QPointF(*b))
        # Flèches de sens ; aucune hachure ni passage piéton ajouté.
        for x,y,a in ((215,394,0),(200,327,180),(910,406,0),
                      (911,337,180),(488,145,90),(560,142,-90),
                      (488,575,90),(560,566,-90),(220,591,-39)):
            dessiner_fleche(p,x,y,a)

    def panneau(self,p,x,y,texte):
        """Dessine un panneau portant le texte fourni."""
        p.save()
        font=QFont('Segoe UI',12,QFont.Weight.Bold)
        p.setFont(font)
        metrics=p.fontMetrics()
        w=metrics.horizontalAdvance(texte)+24
        r=QRectF(x-w/2,y-17,w,34)
        p.setPen(QPen(QColor('#ffffff'),2))
        p.setBrush(QColor('#112f50'))
        p.drawRoundedRect(r,8,8)
        p.setPen(QColor('#ffffff'))
        p.drawText(r,Qt.AlignmentFlag.AlignCenter,texte)
        p.restore()

    def panneaux(self,p):
        """Affiche les noms des routes autour du carrefour."""
        self.panneau(p,520,35,'Av. d’Alsace · N')
        self.panneau(p,520,620,'Av. d’Alsace · S')
        self.panneau(p,152,275,'Rue de la Semm · O')
        self.panneau(p,907,286,'Rue de la Semm · E')
        self.panneau(p,163,630,'Av. de Fribourg')
        p.setPen(QPen(QColor('#29466b'),3))
        p.drawLine(QPointF(44,92),QPointF(44,47))
        p.drawLine(QPointF(44,47),QPointF(35,61))
        p.drawLine(QPointF(44,47),QPointF(53,61))
        p.setPen(QColor('#112f50'))
        p.setFont(QFont('Segoe UI',14,QFont.Weight.Bold))
        p.drawText(36,37,'N')

    def ambulance_trace(self,p):
        """Dessine le trajet de référence de l’ambulance."""
        from simulation import TRAJETS
        path=QPainterPath()
        pts=TRAJETS['O_E'].points
        path.moveTo(QPointF(*pts[0]))
        for xy in pts[1:]:
            path.lineTo(QPointF(*xy))
        pen=QPen(QColor('#ed5064'),5,Qt.PenStyle.DashLine)
        pen.setDashPattern([9,6])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        dessiner_fleche_rouge(p,960,396)

    def trajets_pedagogiques(self,p):
        """Affiche les trajectoires secondaires pour expliquer les mouvements."""
        from simulation import TRAJETS
        for cle, col in (('O_S','#5fb7eb'),('SO_E','#b294d8'),('E_N','#ead169')):
            points=TRAJETS[cle].points
            path=QPainterPath()
            path.moveTo(QPointF(*points[0]))
            for xy in points[1:]:
                path.lineTo(QPointF(*xy))
            p.setPen(QPen(QColor(col),3,Qt.PenStyle.DashLine))
            p.drawPath(path)

    def feux(self,p):
        """Dessine les feux avec les couleurs données par le contrôleur."""
        etats=self.fenetre.sim.controle.etats()
        for nom,(x,y) in FEUX_POSITION.items():
            p.save()
            p.setPen(QPen(QColor('#dbe5f0'),2))
            p.setBrush(QColor('#102b4a'))
            p.drawRoundedRect(QRectF(x-15,y-19,30,48),5,5)
            for i,(c,nom_c) in enumerate((('#ed5664','rouge'),
                                          ('#f7c84c','orange'),('#36d78b','vert'))):
                col=QColor(c) if etats[nom]==nom_c else QColor('#344455')
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawEllipse(QPointF(x,y-9+i*13),5.8,5.8)
            p.setPen(QColor('#163251'))
            p.setBrush(QColor('#ffffff'))
            p.drawRoundedRect(QRectF(x+20,y-10,39,26),6,6)
            p.setFont(QFont('Segoe UI',13,QFont.Weight.Bold))
            p.drawText(QRectF(x+20,y-10,39,26),Qt.AlignmentFlag.AlignCenter,nom)
            p.restore()

    def vehicules(self,p):
        """Dessine les véhicules à leur position simulée."""
        for v in self.fenetre.sim.vehicules:
            x,y,angle=v.position()
            if -25<=x<=1065 and -25<=y<=690:
                p.save()
                p.translate(x,y)
                p.rotate(angle)
                w=38 if v.ambulance else 32
                h=22 if v.ambulance else 19
                p.setPen(QPen(QColor('#20344e'),1.8))
                p.setBrush(QColor(v.couleur))
                p.drawRoundedRect(QRectF(-w/2,-h/2,w,h),5,5)
                p.setBrush(QColor('#a8d5ee'))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(w/2-10,-h/2+3,6,h-6),2,2)
                if v.ambulance:
                    p.fillRect(QRectF(-11,-2,15,4),QColor('#df4554'))
                    p.fillRect(QRectF(-5,-8,4,16),QColor('#df4554'))
                    p.setBrush(QColor('#4cb4ff'))
                    p.drawEllipse(QPointF(-12,-h/2-5),4,4)
                p.restore()


def dessiner_fleche_rouge(p,x,y):
    """Dessine la flèche indiquant le parcours de l’ambulance."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('#ed5064'))
    p.drawPolygon(QPolygonF([QPointF(x-5,y-9),QPointF(x+12,y),QPointF(x-5,y+9)]))
    p.restore()


class Fenetre(QMainWindow):
    """Présente la simulation locale et les commandes de comparaison."""
    def __init__(self):
        """Initialise la simulation, le minuteur et les composants de la fenêtre."""
        super().__init__()
        self.setWindowTitle('SAÉ 3.02 — Jamais2sans3 | Carrefour intelligent')
        self.resize(1430,910)
        self.setMinimumSize(1010,670)
        self.scenario_config=charger_scenario('S02')
        self.sim=Simulation(priorite=True, scenario=self.scenario_config)
        self.en_cours=False
        self.speed=1
        self.resultats=None
        self.timer=QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)
        self.construire_interface()
        self.rafraichir()

    def etiquette(self,txt,objet=''):
        """Crée une étiquette Qt avec son texte et son nom de style."""
        l=QLabel(txt)
        if objet:
            l.setObjectName(objet)
        return l

    def construire_interface(self):
        """Construit la fenêtre, les boutons et le panneau des résultats."""
        root=QWidget()
        self.setCentralWidget(root)
        colonne=QVBoxLayout(root)
        colonne.setContentsMargins(20,18,20,16)
        colonne.setSpacing(12)
        titre=self.etiquette('CARREFOUR INTELLIGENT  ·  SAÉ 3.02','titre')
        colonne.addWidget(titre)
        sous=self.etiquette('Jamais2sans3  ·  Schéma hypothétique inspiré du carrefour Crédit Agricole / IUT de Colmar','sous')
        colonne.addWidget(sous)

        outils=QHBoxLayout()
        self.choix_scenario=QComboBox()
        for sid, label in [('S01','Ambulance seule'), ('S02','Trafic croisé'), ('S03','File devant ambulance')]:
            self.choix_scenario.addItem(f'{sid} - {label}', sid)
        self.choix_scenario.setCurrentIndex(1)
        self.choix_scenario.currentIndexChanged.connect(self.changer_scenario)
        outils.addWidget(self.choix_scenario)
        self.demarrer=QPushButton('▶  Démarrer')
        self.demarrer.clicked.connect(self.demarrer_sim)
        self.pause=QPushButton('⏸  Pause')
        self.pause.clicked.connect(self.mettre_pause)
        self.reset=QPushButton('↺  Recommencer')
        self.reset.clicked.connect(self.recommencer)
        self.priorite=QCheckBox('Priorité ambulance active')
        self.priorite.setChecked(True)
        self.priorite.toggled.connect(self.changer_priorite)
        self.voir_trajets=QCheckBox('Trajectoires secondaires')
        self.voir_trajets.toggled.connect(lambda: self.carte.update())
        self.vitesse_label=self.etiquette('Vitesse ×1')
        self.vitesse=QSlider(Qt.Orientation.Horizontal)
        self.vitesse.setRange(1,4)
        self.vitesse.setValue(1)
        self.vitesse.setFixedWidth(95)
        self.vitesse.valueChanged.connect(self.changer_vitesse)
        for bouton in (self.demarrer,self.pause,self.reset):
            outils.addWidget(bouton)
        outils.addSpacing(12)
        outils.addWidget(self.priorite)
        outils.addWidget(self.voir_trajets)
        outils.addStretch()
        outils.addWidget(self.vitesse_label)
        outils.addWidget(self.vitesse)
        colonne.addLayout(outils)

        corps=QHBoxLayout()
        corps.setSpacing(14)
        self.carte=CarteCarrefour(self)
        self.carte.setObjectName('carte')
        corps.addWidget(self.carte, 5)

        panneau=QFrame()
        panneau.setObjectName('panneau')
        panneau.setFixedWidth(265)
        pv=QVBoxLayout(panneau)
        pv.setContentsMargins(17,16,17,16)
        pv.setSpacing(8)
        pv.addWidget(self.etiquette('ÉTAT DE LA SIMULATION','rubrique'))
        self.etat=self.etiquette('Prête','normal')
        pv.addWidget(self.etat)
        self.temps=self.etiquette('Temps simulé : 0,00 s')
        pv.addWidget(self.temps)
        self.phase=self.etiquette('Cycle normal')
        self.phase.setWordWrap(True)
        pv.addWidget(self.phase)
        pv.addSpacing(15)
        pv.addWidget(self.etiquette('FEUX TRICOLORES','rubrique'))
        self.feux_labels={}
        for nom in ('F1','F2','F3','F4','F5'):
            label=self.etiquette(f'{nom}  ·  {NOMS_FEUX[nom]}')
            pv.addWidget(label)
            self.feux_labels[nom]=label
        pv.addSpacing(15)
        pv.addWidget(self.etiquette('ÉVÉNEMENTS','rubrique'))
        self.journal=self.etiquette('Aucun événement')
        self.journal.setWordWrap(True)
        self.journal.setAlignment(Qt.AlignmentFlag.AlignTop)
        pv.addWidget(self.journal, 1)
        pv.addWidget(self.etiquette('Contrôle local simulé\nServeur TCP de Youssef : à connecter','note'))
        corps.addWidget(panneau,1)
        colonne.addLayout(corps,1)

        pied=QFrame()
        pied.setObjectName('panneau')
        ligne=QHBoxLayout(pied)
        ligne.setContentsMargins(16,12,16,12)
        self.sans=self.etiquette('Sans priorité : —','stat')
        self.avec=self.etiquette('Avec priorité : —','stat')
        self.gain=self.etiquette('Gain : —','stat')
        self.comparer=QPushButton('Comparer le même scénario')
        self.comparer.clicked.connect(self.comparer_scenarios)
        for v in (self.sans,self.avec,self.gain):
            ligne.addWidget(v)
        ligne.addStretch()
        ligne.addWidget(self.comparer)
        colonne.addWidget(pied)

        self.setStyleSheet('''
            QWidget {font-family: 'Segoe UI', Arial; font-size: 13px; color: #18334f; background: #f2f5f8;}
            QLabel#titre {font-size: 23px; font-weight: 800; color: #0c2c4c;}
            QLabel#sous {font-size: 12px; color: #60768b;}
            QLabel#rubrique {font-size: 12px; font-weight: 800; color: #3f647e; margin-top: 3px;}
            QLabel#normal {font-size: 17px; font-weight: 700; color: #167d61;}
            QLabel#stat {font-size: 14px; font-weight: 700;}
            QLabel#note {font-size: 11px; color: #718296; background: #edf3f8; padding: 9px; border-radius: 8px;}
            QFrame#panneau {background: #ffffff; border: 1px solid #d4dfe9; border-radius: 12px;}
            QFrame#panneau QLabel {background: transparent;}
            QWidget#carte {border: 1px solid #b7c9d7; border-radius: 12px;}
            QPushButton {background: #153b62; color: white; padding: 10px 15px; border: 0; border-radius: 8px; font-weight: 700;}
            QPushButton:hover {background: #235a88;}
            QPushButton:disabled {background: #a3b3c1;}
            QCheckBox {spacing: 8px;}
        ''')

    def changer_scenario(self, index):
        """Charge un autre scénario et efface les résultats de la sélection précédente."""
        self.scenario_config=charger_scenario(self.choix_scenario.currentData())
        self.recommencer()

    def changer_priorite(self, actif):
        # Changer le mode recommence le scénario pour conserver des essais comparables.
        """Réinitialise l’essai après un changement du mode de priorité."""
        self.recommencer()

    def changer_vitesse(self, vitesse):
        """Modifie la vitesse d’affichage sans changer le pas du temps simulé."""
        self.speed=vitesse
        self.vitesse_label.setText(f'Vitesse ×{vitesse}')

    def demarrer_sim(self):
        """Démarre ou reprend la simulation avec le minuteur Qt."""
        if self.sim.ambulance_terminee is not None:
            self.recommencer()
        self.en_cours=True
        self.timer.start()
        self.rafraichir()

    def mettre_pause(self):
        """Arrête le minuteur en conservant l’état courant de la simulation."""
        self.en_cours=False
        self.timer.stop()
        self.rafraichir()

    def recommencer(self):
        """Réinitialise le scénario sélectionné et efface les résultats affichés."""
        self.timer.stop()
        self.en_cours=False
        self.sim=Simulation(self.priorite.isChecked(), self.scenario_config)
        self.resultats=None
        self.rafraichir()

    def tick(self):
        """Avance la simulation puis arrête le minuteur si l’ambulance est arrivée."""
        if not self.en_cours:
            return
        for _ in range(self.speed):
            self.sim.avancer(DT)
            if self.sim.ambulance_terminee is not None:
                self.en_cours=False
                self.timer.stop()
                break
        self.rafraichir()

    def comparer_scenarios(self):
        """Compare le scénario sélectionné sans et avec priorité."""
        self.resultats=comparer(self.scenario_config)
        self.rafraichir()

    def rafraichir(self):
        """Actualise les états, le journal et les résultats dans la fenêtre."""
        sim=self.sim
        if sim.ambulance_terminee is not None:
            texte='Essai terminé'
        elif self.en_cours:
            texte='Simulation en cours'
        elif sim.t>0:
            texte='En pause'
        else:
            texte='Prête'
        self.etat.setText(texte)
        self.temps.setText(f'Temps simulé : {sim.t:.2f} s')
        self.phase.setText(sim.controle.nom_phase)
        etats=sim.controle.etats()
        emoji={'rouge':'🔴','orange':'🟠','vert':'🟢'}
        for nom,label in self.feux_labels.items():
            label.setText(f'{emoji[etats[nom]]}  {nom} · {NOMS_FEUX[nom]}')
        self.journal.setText('\n'.join(sim.journal[-5:]))
        self.pause.setEnabled(self.en_cours)
        self.demarrer.setEnabled(not self.en_cours)
        if self.resultats is not None:
            sans,avec,gain=self.resultats
            self.sans.setText(f'Sans priorité : {sans:.2f} s')
            self.avec.setText(f'Avec priorité : {avec:.2f} s')
            self.gain.setText(f'Gain simulé : {gain:+.2f} s')
        else:
            self.sans.setText('Sans priorité : —')
            self.avec.setText('Avec priorité : —')
            self.gain.setText('Gain : —')
        self.carte.update()


def main():
    """Crée l’application Qt et ouvre la fenêtre de simulation locale."""
    app=QApplication(sys.argv)
    f=Fenetre()
    f.show()
    sys.exit(app.exec())


if __name__=='__main__':
    main()
