from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from .. import fechas
from ..dinero import redondear
from ..models import Presupuesto, Transaccion
from ..servicios.esfera import estado_esfera
from ..servicios.mes import CLAVES_NUMEROS, numeros_mes, numeros_meses, resumen_mes, salud_financiera
from ..servicios.panel import insights_panel
from ..templatetags.moneda import money


class RedondearTests(SimpleTestCase):

    def test_la_mitad_sube(self):
        self.assertEqual(redondear(Decimal('2.5')), 3)
        self.assertEqual(redondear(Decimal('3.5')), 4)
        self.assertEqual(redondear(Decimal('-2.5')), -3)
        self.assertEqual(redondear(2.5), 3)

    def test_sin_decimales_devuelve_entero(self):
        self.assertIsInstance(redondear(Decimal('10.4')), int)
        self.assertEqual(redondear(None), 0)

    def test_con_decimales(self):
        self.assertEqual(redondear(Decimal('1.005'), 2), Decimal('1.01'))
        self.assertEqual(redondear(Decimal('12.25'), 1), Decimal('12.3'))

    def test_money_usa_el_mismo_redondeo(self):
        self.assertEqual(money(Decimal('1500.5')), '$1.501')
        self.assertEqual(money(Decimal('10.005'), 'US$'), 'US$10,01')
        self.assertEqual(money(Decimal('1.999'), '€'), '€2,00')


class MesEnDecimalTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = fechas.hoy()

    def _movimientos(self, fecha=None):
        fecha = fecha or self.hoy
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000'),
                                   categoria='Sueldo', fecha=fecha)
        for monto in ('0.10', '0.20'):
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                       categoria='Comida', fecha=fecha, pagado=True)

    def test_el_resumen_sale_en_decimal_y_exacto(self):
        self._movimientos()
        r = resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        for clave in ('ingresos', 'gastos', 'total_cuotas_mes', 'comprometido', 'disponible', 'por_dia'):
            self.assertIsInstance(r[clave], Decimal, clave)
        self.assertEqual(r['gastos'], Decimal('0.30'))
        self.assertEqual(r['disponible'], Decimal('999.70'))
        self.assertIsInstance(r['pct_gastado'], int)

    def test_los_numeros_guardados_siguen_en_decimal(self):
        self._movimientos()
        primera = numeros_mes(self.ana, self.hoy.year, self.hoy.month)
        segunda = numeros_mes(self.ana, self.hoy.year, self.hoy.month)
        for datos in (primera, segunda):
            for clave in CLAVES_NUMEROS:
                self.assertIsInstance(datos[clave], Decimal, clave)
        self.assertEqual(segunda['gastos'], Decimal('0.30'))

    def test_los_meses_pasados_salen_en_decimal(self):
        pasado = self.hoy.replace(day=1) - timedelta(days=1)
        self._movimientos(pasado)
        datos = numeros_meses(self.ana, [(pasado.year, pasado.month)])[(pasado.year, pasado.month)]
        for clave in CLAVES_NUMEROS:
            self.assertIsInstance(datos[clave], Decimal, clave)
        self.assertEqual(datos['disponible'], Decimal('999.70'))

    def test_esfera_salud_e_ideas_aceptan_decimal(self):
        self._movimientos()
        presupuesto = Presupuesto.objects.create(usuario=self.ana, limite_mensual=Decimal('1000'))
        r = resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        esfera = estado_esfera(self.ana, r, presupuesto, self.hoy.month, True)
        self.assertEqual(esfera['estado'], 'verde')
        self.assertEqual(esfera['pct'], 0)
        self.assertIsInstance(salud_financiera(self.ana, resumen_actual=r)['salud_score'], int)
        ideas, _ = insights_panel(r, [Decimal('100'), Decimal('150')], [], [], presupuesto)
        self.assertTrue(any('50% más' in i['texto'] for i in ideas))
