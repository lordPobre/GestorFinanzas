from django.test import SimpleTestCase

from ..cartolas import BANCOS
from ..cartolas.base import ErrorCartola, _leer
from .test_cartola_cuentarut import CARTOLA


class EleccionDeBancoTests(SimpleTestCase):

    def test_bancoestado_elegido_lee_cuentarut(self):
        cartola = _leer(CARTOLA, 'estado')
        self.assertEqual(cartola.banco, BANCOS['estado_cuentarut'].nombre)
        self.assertEqual(len(cartola.movimientos), 6)
        self.assertTrue(cartola.cuadra)

    def test_cuentarut_elegido_sigue_igual(self):
        cartola = _leer(CARTOLA, 'estado_cuentarut')
        self.assertEqual(len(cartola.movimientos), 6)

    def test_deteccion_automatica_sigue_igual(self):
        cartola = _leer(CARTOLA)
        self.assertEqual(cartola.banco, BANCOS['estado_cuentarut'].nombre)

    def test_texto_ilegible_mantiene_el_error(self):
        with self.assertRaises(ErrorCartola):
            _leer('esto no es una cartola', 'estado')

    def test_banco_inexistente(self):
        with self.assertRaises(ErrorCartola):
            _leer(CARTOLA, 'no_existe')
