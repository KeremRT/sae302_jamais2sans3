"""Decoupage des lignes TCP, optionnel pour le serveur de Youssef."""

import json

from .validation import DonneesInvalides


def _unique_keys(pairs):
    """Construit un dictionnaire JSON en refusant les clés dupliquées."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise DonneesInvalides(f'Cle JSON dupliquee : {key}.')
        result[key] = value
    return result


def _reject_constant(value):
    """Refuse les constantes JSON non finies telles que NaN."""
    raise DonneesInvalides(f'Constante JSON interdite : {value}.')


class LecteurJSONL:
    """Une instance par connexion. En cas d'erreur, fermer cette connexion.

    feed est un generateur : traiter les messages dans l'ordre ; un message
    valide precedant une ligne invalide reste disponible pour traitement.
    """
    MAX_LINE = 16384

    def __init__(self):
        """Initialise le tampon qui conserve les fragments de messages TCP."""
        self._buffer = bytearray()

    def feed(self, data):
        """Reconstitue les lignes JSON reçues par fragments et produit les messages complets."""
        if not isinstance(data, bytes):
            raise DonneesInvalides('Le lecteur attend des octets TCP.')
        self._buffer.extend(data)
        while b'\n' in self._buffer:
            raw, _, rest = self._buffer.partition(b'\n')
            self._buffer = bytearray(rest)
            if not raw or len(raw) > self.MAX_LINE:
                raise DonneesInvalides('Ligne JSON vide ou trop longue.')
            try:
                obj = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_keys,
                                 parse_constant=_reject_constant)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise DonneesInvalides('Ligne JSON invalide.') from exc
            if not isinstance(obj, dict):
                raise DonneesInvalides('Objet JSON attendu.')
            yield obj
        if len(self._buffer) > self.MAX_LINE:
            raise DonneesInvalides('Ligne trop longue sans terminateur LF.')

    def finish(self):
        """Vérifie qu’aucun message incomplet ne reste à la déconnexion."""
        if self._buffer:
            raise DonneesInvalides('Connexion fermee au milieu d un message JSON.')
