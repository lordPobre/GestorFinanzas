from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from .. import fechas
from ..servicios.mes import resumen_mes
from ..views.panel import _plata


class PlataTests(SimpleTestCase):

    def test_pesos_sin_centavos(self):
        plata = _plata('$')
        self.assertEqual(plata(Decimal('10.5')), 11)
        self.assertIsInstance(plata(Decimal('10.5')), int)

    def test_otras_monedas_con_centavos(self):
        plata = _plata('US$')
        self.assertEqual(plata(Decimal('10.005')), Decimal('10.01'))
        self.assertEqual(plata(Decimal('-3.125')), Decimal('-3.13'))


class ResumenSinExactoTests(TestCase):

    def test_el_resumen_ya_no_trae_exacto(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        hoy = fechas.hoy()
        r = resumen_mes(ana, hoy.year, hoy.month)
        self.assertNotIn('exacto', r)
        self.assertIsInstance(r['disponible'], Decimal)
