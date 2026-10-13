from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import TestCase

from ..analisis import analizar_finanzas
from ..models import Transaccion
from ..plan import armar_plan


class MesNormalIgualAlPlan(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.inicio = date.today().replace(day=1)

    def _mov(self, meses_atras, tipo, monto):
        Transaccion.objects.create(usuario=self.ana, tipo=tipo, monto=Decimal(monto),
                                   categoria='Otros', fecha=self.inicio - relativedelta(months=meses_atras))

    def test_mismas_cifras_que_el_plan(self):
        self._mov(1, 'INGRESO', '900000')
        self._mov(1, 'EGRESO', '300000')
        self._mov(2, 'INGRESO', '1100000')
        self._mov(2, 'EGRESO', '500000')
        a, p = analizar_finanzas(self.ana), armar_plan(self.ana)
        self.assertEqual(a['ingreso_mensual'], p['ingreso'])
        self.assertEqual(a['gasto_mensual'], p['gasto'])
        self.assertEqual(a['compromisos_mes'], p['compromisos'])
        self.assertEqual(a['meses_base'], p['meses_base'])

    def test_meses_vacios_no_bajan_el_promedio(self):
        self._mov(1, 'INGRESO', '1000000')
        self._mov(1, 'EGRESO', '400000')
        a = analizar_finanzas(self.ana)
        self.assertEqual(a['gasto_mensual'], 400000)
        self.assertEqual(a['meses_base'], 1)
        self.assertTrue(a['pocos_datos'])
