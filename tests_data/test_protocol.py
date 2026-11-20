import json
import unittest

from sae_data.protocol import LecteurJSONL
from sae_data import DonneesInvalides


class ProtocolTests(unittest.TestCase):
    """Vérifie le découpage et le rejet des messages JSON invalides."""
    def test_fragments_multioctets_et_plusieurs_messages(self):
        """Vérifie la réception de messages UTF-8 fragmentés et de plusieurs lignes."""
        data = (json.dumps({'texte': 'été'}, ensure_ascii=False) + '\n{}\n').encode()
        lecteur = LecteurJSONL()
        result = []
        for byte in data:
            result.extend(lecteur.feed(bytes([byte])))
        lecteur.finish()
        self.assertEqual(result, [{'texte': 'été'}, {}])

    def test_lignes_invalides(self):
        """Vérifie le rejet des lignes JSON invalides."""
        for data in [b'[]\n', b'\n', b'{"a":NaN}\n', b'{"a":1,"a":2}\n', b'\xff\n']:
            with self.subTest(data=data), self.assertRaises(DonneesInvalides):
                list(LecteurJSONL().feed(data))

    def test_message_tronque(self):
        """Vérifie le rejet d’un message incomplet à la fermeture."""
        lecteur = LecteurJSONL()
        list(lecteur.feed(b'{'))
        with self.assertRaises(DonneesInvalides):
            lecteur.finish()

    def test_taille_limite(self):
        """Vérifie la limite de taille des messages."""
        for data in [b' ' * 16385, b' ' * 16385 + b'\n']:
            with self.subTest(size=len(data)), self.assertRaises(DonneesInvalides):
                list(LecteurJSONL().feed(data))
