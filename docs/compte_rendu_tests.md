# Compte rendu des tests — Huy-Ming Banchongphanith

## Périmètre et protocole

Mesures produites le 12 novembre 2026 avec le moteur original de Kerem, sans modification de l'interface, des feux ou de la circulation. Les fichiers sont dans `scenarios/`, `sql/` et `docs/`. Les UUID, configurations complètes et empreinte SHA-256 du moteur figurent dans `resultats_mesures.json`.

- S01, `scenario_urgence.json` : ambulance seule Ouest → Est à 5 s.
- S02, `scenario_normal.json` : quatre véhicules Nord/Sud à 0 et 1 s ; ambulance Ouest → Est à 2 s.
- S03, `scenario_dense.json` : trois véhicules Ouest → Est à 0, 1 et 2 s, un Nord → Sud à 0 s ; ambulance derrière la file à 5 s. « Dense » désigne ici une file locale, pas une mesure représentative d'une ville.

Vitesses : 61 pixels/s pour les véhicules ordinaires, 74 pour l'ambulance. Carrefour initialement vide ; positions à l'apparition : début du trajet (`s=0`). Feux F1/F3 verts, F2/F4/F5 rouges. Pas fixe de 0,05 s. Géométrie, phases et horaires sont enregistrés dans les JSON. Les deux essais utilisent les mêmes données et des instances neuves du moteur.

Le départ mesuré est le début du pas dans lequel l'ambulance apparaît ; l'arrivée est le seuil du moteur original, longueur du trajet moins 15 pixels. Ce choix respecte son ordre de calcul (création puis mouvement dans le pas). Il peut décaler le départ d'un pas par rapport à l'horaire demandé. Durée = arrivée − départ, gain = durée SANS − durée AVEC ; un gain négatif reste négatif. Les attentes avant apparition ne sont pas incluses. Une limite de 120 s produit un essai interrompu, sans durée finale ni gain comparable.

## Résultats réellement exécutés

| Scénario | Sans priorité (s) | Avec priorité (s) | Gain (s) |
|---|---:|---:|---:|
| S02 | 23.45 | 13.15 | +10.30 |
| S03 | 24.80 | 17.50 | +7.30 |
| S01 | 20.45 | 13.15 | +7.30 |

Ces résultats proviennent du moteur local, avec enregistrement et relecture MariaDB réussis. Ils ne viennent pas du tableau fictif envoyé par Kerem. La priorité réduit l'attente au feu ; dans S03, les véhicules devant l'ambulance limitent l'amélioration. Le détail des départs et arrivées est conservé dans le JSON associé.

## Vérifications

- Deux tests de scénarios réussis : répétition de chaque paire, paramètres inchangés, identifiants distincts, durée et gain recalculés, interruption avant arrivée.
- Trente tests de données réussis sur MariaDB 13.0.2 : insertions, relecture, gains positif/nul/négatif, essais incomplets, horodatages invalides, transactions et rollback, doublons, événements concurrents et séparation des essais.
- `donnees_test.sql` exécuté dans la base de test : insertions et SELECT vérifiés, transaction validée, gain fictif +3 s.

## Difficultés et limites

Le moteur initial prend son scénario dans une constante Python. Le script de Huy-Ming charge donc une instance isolée de ce module et remplace uniquement son calendrier en mémoire. L'interface reste inchangée et ne sélectionne pas encore ces JSON. Une différence d'encodage Windows a été détectée lors des tests : la lecture des JSON utilise explicitement UTF-8 afin de conserver une empreinte identique.

La priorité est locale ; le serveur TCP n'est pas encore raccordé. Les pixels ne sont pas des mètres. Le moteur ne gère pas complètement les conflits de trajectoires, les fusions et l'occupation du carrefour à chaque changement de phase. Les configurations évitent les apparitions simultanées sur une même voie ; le moteur ne possède pas de file d'entrée hors champ. Ces tests ne démontrent ni une absence de collision, ni une aptitude au déploiement réel.

## État des tâches et travail commun restant

Les scénarios, comparaisons en script, calculs, tables, scripts SQL, sauvegarde directe MariaDB, tests et documentation sont fournis. La tâche 6 est réalisée pour le script et reste à finaliser pour l'application et le serveur avec Kerem et Youssef. La tâche 9 reste également ouverte pour les vérifications communes et la soutenance. Aucun temps réel de travail collectif n'est inventé : les relevés hebdomadaires n'ont pas été fournis ici.

## Usage de l'IA

ChatGPT/Codex a aidé à adapter les scénarios, préparer le script de comparaison, reprendre le module MariaDB et ses tests, puis rédiger ce compte rendu. Prompt structurant : « mon travail c'était scenario et sql, met ma partie dans ses dossiers ». La contrainte appliquée est de ne modifier ni le moteur ni l'interface de Kerem. Les sorties ont été vérifiées par exécution et relecture ; les données fictives sont séparées des mesures. Aucun identifiant privé MariaDB n'est publié. Le groupe doit comprendre et relire le code avant de le présenter ; les résultats d'un simulateur simplifié ne doivent pas être présentés comme une preuve de sécurité routière.
