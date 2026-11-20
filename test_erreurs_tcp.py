r"""Petits tests manuels du serveur TCP (aucune écriture MariaDB).

Sur Windows :
    .\.venv\Scripts\python.exe test_erreurs_tcp.py --host 192.168.56.101

Démarrer serveur_central.py sur Debian avant d'exécuter ce script.
"""

import argparse
import socket


def tester(host, port, nom, contenu):
    """Envoie un message TCP de test et affiche la réponse ou l’erreur reçue."""
    print('\n' + nom)
    try:
        with socket.create_connection((host, port), timeout=5) as client:
            client.settimeout(5)
            client.sendall(contenu.encode('utf-8'))
            reponse = client.recv(4096)
            if reponse:
                print('Réponse :', reponse.decode('utf-8').strip())
            else:
                print('Le serveur a fermé cette connexion.')
    except (OSError, UnicodeError) as erreur:
        print('Erreur de connexion :', erreur)


def main():
    """Envoie des messages valides et invalides au serveur pour un contrôle manuel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='192.168.56.101')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    # Chaque envoi utilise une nouvelle connexion : le serveur BUT2
    # s'occupe d'un client à la fois.
    tester(args.host, args.port, '1. Vérifier que le serveur répond',
           '{"type":"ping"}\n')
    tester(args.host, args.port, '2. Refuser un message inconnu',
           '{"type":"commande_inconnue"}\n')
    tester(args.host, args.port, '3. Refuser le scénario S99',
           '{"type":"create_comparison","scenario_id":"S99"}\n')
    tester(args.host, args.port, '4. JSON incorrect : connexion fermée',
           '{"type":\n')
    tester(args.host, args.port, '5. Vérifier que le serveur répond encore',
           '{"type":"ping"}\n')


if __name__ == '__main__':
    main()
