# Compte rendu des tests — Huy-Ming

## Scénarios

- **Urgence (S01)** : ambulance seule, arrivée à 5 s, Ouest vers Est.
- **Normal (S02)** : quatre voitures Nord/Sud à 0 et 1 s ; ambulance à 2 s.
- **Dense (S03)** : trois voitures Ouest vers Est à 0, 1 et 2 s, une Nord vers Sud à 0 s ; ambulance derrière elles à 5 s.

Les voitures roulent à 61 pixels/s et l'ambulance à 74 pixels/s. Toutes apparaissent au début de leur trajet. Initialement, F1/F3 sont verts et F2/F4/F5 rouges. Les JSON sont en version 4, correspondant au format simplifié.

## Méthode

Le script utilise le moteur de Kerem sans modifier ses fichiers. Chaque scénario est exécuté en deux essais successifs SANS et AVEC priorité : mêmes véhicules, horaires, vitesses et trajets ; seul le booléen de priorité change.

Le départ est le début du pas de calcul où l'ambulance apparaît. L'arrivée est le seuil prévu par le moteur : longueur du trajet moins 15 pixels. Le pas vaut 0,05 s. La durée est arrivée − départ ; le gain est durée SANS − durée AVEC. Au-delà de 120 s, l'essai est interrompu, sans durée finale.

## Résultats mesurés le 12 novembre 2026

| Scénario | Sans (s) | Avec (s) | Gain (s) |
|---|---:|---:|---:|
| Urgence | 20,45 | 13,15 | +7,30 |
| Normal | 23,45 | 13,15 | +10,30 |
| Dense | 24,80 | 17,50 | +7,30 |

Ces valeurs ont été recalculées avec le code simplifié, sauvegardées puis relues dans MariaDB. Les conditions et identifiants sont dans `resultats_mesures.json`. La priorité réduit l'attente au feu ; la file de véhicules devant l'ambulance limite le gain dans le scénario dense.

## Tests effectués

- Trois tests automatisés : reproductibilité des trois scénarios, calcul des gains positif/négatif/nul ou incomplet, interruption.
- Vérifications MariaDB : sauvegarde et relecture, perte de temps conservée, essai incomplet et rollback en cas de durée incorrecte.
- Les données fictives de `donnees_test.sql` sont marquées EXEMPLE, séparément des mesures SIMULATION.

## Limites et travail restant

La version simplifiée n'utilise plus de gestionnaire d'événements réseau ni de tests concurrents. Elle sauvegarde directement les deux essais dans une transaction : soit tout est enregistré, soit rien. Les contrôles essentiels et les requêtes SQL paramétrées sont conservés.

Le programme est pédagogique : les pixels ne sont pas des mètres, le contrôleur est local, et tous les conflits de circulation ne sont pas modélisés. « Dense » décrit une file locale, pas le trafic d'une ville entière. Les JSON sont destinés au moteur actuel ; un changement de ses trajets ou de ses règles demande de vérifier les scénarios à nouveau.

Les tâches de scénarios, calculs, SQL, sauvegarde par script et documentation sont réalisées. Le raccordement à l'interface de Kerem et au serveur de Youssef, les tests communs et la soutenance restent à faire ensemble.

## Aide de l'IA

ChatGPT/Codex a aidé à simplifier les fonctions, les JSON et la documentation à la demande de Huy-Ming : « fais les codes niveau BUT2 [...] rend le vraiment simple ». Les résultats ont été vérifiés par exécution. Huy-Ming doit comprendre et pouvoir expliquer chaque fonction. Aucun mot de passe n'est publié et aucune aptitude à la sécurité routière réelle n'est revendiquée.
