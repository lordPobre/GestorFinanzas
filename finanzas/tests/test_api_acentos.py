import json

from django.test import TestCase

from finanzas.views.api import _texto_cuerpo


class CuerpoConAcentosTests(TestCase):
    def test_utf8(self):
        self.assertEqual(json.loads(_texto_cuerpo('{"texto":"café"}'.encode('utf-8')))['texto'], 'café')

    def test_utf8_con_bom(self):
        crudo = b'\xef\xbb\xbf' + '{"texto":"café"}'.encode('utf-8')
        self.assertEqual(json.loads(_texto_cuerpo(crudo))['texto'], 'café')

    def test_latin1_de_powershell(self):
        self.assertEqual(json.loads(_texto_cuerpo('{"texto":"5 lucas en café"}'.encode('cp1252')))['texto'], '5 lucas en café')
