import json

from .validation import DonneesInvalides


# On refuse les clés qui apparaissent deux fois dans le même objet JSON.
def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DonneesInvalides(f'Cle JSON dupliquee : {key}.')
        result[key] = value
    return result


# On refuse les valeurs comme NaN ou l’infini.
def _reject_constant(value):
    raise DonneesInvalides(f'Constante JSON interdite : {value}.')


# On garde les morceaux reçus jusqu’à obtenir un message complet.
class LecteurJSONL:
    MAX_LINE = 16384

    # On commence avec un tampon vide pour cette connexion.
    def __init__(self):
        self._buffer = bytearray()

    # On ajoute les octets reçus et on lit chaque ligne JSON complète.
    def feed(self, data):
        if not isinstance(data, bytes):
            raise DonneesInvalides('Le lecteur attend des octets TCP.')
        # On ajoute les nouveaux octets à ceux qui restent du dernier appel.
        self._buffer.extend(data)
        # Chaque retour à la ligne marque la fin d’un message.
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
            # On donne ce message à l’appelant avant de passer au suivant.
            yield obj
        if len(self._buffer) > self.MAX_LINE:
            raise DonneesInvalides('Ligne trop longue sans terminateur LF.')

    # À la déconnexion, on vérifie qu’il ne reste pas de message coupé.
    def finish(self):
        if self._buffer:
            raise DonneesInvalides('Connexion fermee au milieu d un message JSON.')
