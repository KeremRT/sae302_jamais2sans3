import json
import unittest

from sae_data.protocol import LecteurJSONL
from sae_data import DonneesInvalides


class ProtocolTests(unittest.TestCase):
    def test_fragments_multioctets_et_plusieurs_messages(self):
        data = (json.dumps({'texte': 'été'}, ensure_ascii=False) + '\n{}\n').encode()
        lecteur = LecteurJSONL()
        result = []
        for byte in data:
            result.extend(lecteur.feed(bytes([byte])))
        lecteur.finish()
        self.assertEqual(result, [{'texte': 'été'}, {}])

    def test_lignes_invalides(self):
        for data in [b'[]\n', b'\n', b'{"a":NaN}\n', b'{"a":1,"a":2}\n', b'\xff\n']:
            with self.subTest(data=data), self.assertRaises(DonneesInvalides):
                list(LecteurJSONL().feed(data))

    def test_message_tronque(self):
        lecteur = LecteurJSONL()
        list(lecteur.feed(b'{'))
        with self.assertRaises(DonneesInvalides):
            lecteur.finish()

    def test_taille_limite(self):
        for data in [b' ' * 16385, b' ' * 16385 + b'\n']:
            with self.subTest(size=len(data)), self.assertRaises(DonneesInvalides):
                list(LecteurJSONL().feed(data))
