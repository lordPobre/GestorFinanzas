from decimal import Decimal

from django.test import SimpleTestCase

from ..dinero import suma


class SumaTests(SimpleTestCase):

    def test_suma_exacta_con_centavos(self):
        self.assertEqual(sum([0.1, 0.2]), 0.30000000000000004)
        self.assertEqual(suma([0.1, 0.2]), Decimal('0.3'))
        self.assertEqual(suma([Decimal('19.99')] * 3), Decimal('59.97'))

    def test_acepta_decimales_enteros_floats_y_vacios(self):
        self.assertEqual(suma([Decimal('1000'), 500, 250.5, None]), Decimal('1750.5'))
        self.assertEqual(suma([]), Decimal(0))
        self.assertEqual(round(suma(x for x in [Decimal('1499.5'), Decimal('0.4')])), 1500)
