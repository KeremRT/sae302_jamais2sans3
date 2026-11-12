# Concordance entre le moteur de Kerem et les données de Huy-Ming

Revue et adaptation du 12 novembre 2026, à partir du commit
cba7764e5b413ebf1563c685c767f40868d7d3a4 et du module de données validé précédemment.

## Décision d’intégration

Conserver le dessin, les cinq branches et le contrôleur local de Kerem. Adapter
les scénarios à ce moteur en version 2, sans écraser la version 1 de Huy-Ming.
Ce sont des choix de maquette à reprendre dans le CdC et à convenir dans le groupe.

| Élément | Anciennes fiches v1 | Scénarios intégrés v2 |
|---|---|---|
| Géométrie | 4 branches | 5 branches du dessin de Kerem |
| Ambulance | A1, Sud vers Nord | A1, Ouest vers Est |
| Déplacement | Mètres, accélération/freinage | Pixels, vitesse constante simplifiée |
| Point de référence | Avant du véhicule | Centre du véhicule dessiné |
| Pas | 0,1 s | 0,05 s |
| Chrono | Entrée effective vers sortie | Même principe, sur toute la trajectoire O_E |
| Feux | Cycle de 50 s, priorité sur NS | Cycle de Kerem, priorité sur EO |
| Attente hors zone | Conservée | Entrées retardées si occupées, journalisées |
| Base / messages | UUID, AVEC/SANS, A1, 120 s | Contrat conservé, scenario_version=2 |

Les fichiers JSON figent les trajectoires, le cycle, les règles de priorité,
le pas, les vitesses et le calendrier. Le chargeur refuse une configuration
incompatible au lieu d’en ignorer les paramètres. La cinquième branche est
présente dans la géométrie ; les trois scénarios de base n'y programment pas de
véhicule. Les autres mouvements optionnels restent ceux de Kerem.

## Fiches exécutables

- S01 : A1 à 5 s, sans autre véhicule.
- S02 : N1/S1 à 0 s, N2/S2 à 1 s, A1 à 2 s. Les voitures croisent son axe.
- S03 : O1 à 0 s, O2 à 1 s, O3 à 2 s, A1 à 5 s ; N1 à 0 s. Le test vérifie
  effectivement la présence d’un véhicule immobilisé devant A1 dans les deux modes.

Les voitures ordinaires roulent à 61 pixels/s et A1 à 74 pixels/s. Ce ne sont pas
des vitesses routières calibrées. Les deux modes d'une paire utilisent exactement
la même configuration. L'identifiant de comparaison est commun ; les essais et
événements ont leurs UUID propres.

## Corrections apportées au moteur

Chargement des scénarios, sélection dans Qt, temps fixe calculé à partir du nombre
de pas, mesure arrivée moins entrée effective, arrivée en fin de trajectoire
(au lieu de 15 pixels avant), et attente à l’entrée pour éviter les superpositions.
Les résultats sont effacés lors d’un changement de scénario ou de mode.
La logique des feux de Kerem n’a pas été réécrite.

## Vérifications effectuées

- 9 tests moteur/scénarios réussis, incluant les 4 tests existants de Kerem.
- 30 tests de données/protocole/concurrence réussis avec la base MariaDB de test.
- Trois paires S01/S02/S03 version 2 exécutées, sauvegardées comme SIMULATION et
  relues dans MariaDB ; gain relu identique au gain calculé.

| Scénario v2 | SANS (s) | AVEC (s) | Gain local simulé (s) |
|---|---:|---:|---:|
| S01 | 20,60 | 13,35 | 7,25 |
| S02 | 23,60 | 13,35 | 10,25 |
| S03 | 24,95 | 17,70 | 7,25 |

Ces résultats proviennent du moteur exécuté, et non des anciens exemples 27,40 /
22,00 s. Ils restent conditionnés au modèle simplifié et à son contrôleur local.

## Limites et travail commun restant

Youssef doit raccorder ses sockets et commandes : start_trial, identifiants,
configuration, acquittements après transaction et interruptions réseau. Le
script executer_scenarios.py fournit des événements compatibles mais appelle la
base directement ; il ne prouve pas le fonctionnement du serveur TCP.
L’interface Qt seule ne sauvegarde pas ses essais dans MariaDB.

La sécurité du carrefour n’est pas démontrée par ces tests : le contrôleur de
Kerem attend une durée fixe de tous rouges sans vérifier l’occupation complète
de la zone ; les trajectoires qui fusionnent ne partagent pas toutes une règle
d’espacement. Le retour de priorité n’applique pas l’orange de la fiche v1.
Il faut traiter ces points en groupe avant d’affirmer le respect de toutes les
règles du CdC. Aucun gain routier réel ni certification de sécurité n’est déduit.

## Traçabilité IA

À la demande de Huy-Ming (« verifier que ça concorde [...] faire les scenarios
[...] push le dans le github »), Codex a comparé les deux codes, adapté les
scénarios, écrit le chargeur et le raccordement local, ajouté les tests et
exécuté la validation. Les valeurs publiées sont issues des essais effectués.
Le groupe doit comprendre ces changements et confirmer les choix v2 dans le CdC.
Aucun mot de passe ni fichier privé de configuration n’est inclus.
