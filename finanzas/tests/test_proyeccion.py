from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from .. import fechas
from ..models import Deuda, Suscripcion, Transaccion
from ..servicios.mes import resumen_mes
from ..servicios.proyeccion import proyeccion


class ProyeccionTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = fechas.hoy()
        primero = self.hoy.replace(day=1)
        for atras in (1, 2, 3):
            f = (primero - relativedelta(months=atras)).replace(day=10)
            Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000000'),
                                       categoria='Sueldo', fecha=f)
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('400000'),
                                       categoria='Comida', fecha=f, pagado=True)
        Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('120000'),
                             cuotas_totales=12, fecha_inicio=primero.replace(day=5))
        Suscripcion.objects.create(usuario=self.ana, nombre='Música', monto=Decimal('10000'),
                                   dia_cobro=15, fecha_inicio=primero - timedelta(days=400))

    def test_el_mes_actual_calza_con_inicio(self):
        p = proyeccion(self.ana)
        r = resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        self.assertEqual(len(p['meses']), 4)
        self.assertEqual(p['meses'][0]['libre'], r['disponible'])
        self.assertEqual(p['dias'][-1]['saldo'], r['disponible'])
        self.assertEqual(p['dias'][0]['fecha'], self.hoy)

    def test_los_meses_que_vienen_usan_el_mes_tipico(self):
        p = proyeccion(self.ana)
        futuro = p['meses'][1]
        self.assertEqual(futuro['ingreso'], Decimal('1000000'))
        self.assertEqual(futuro['gasto_variable'], Decimal('390000'))
        self.assertEqual({c['tipo'] for c in futuro['cobros']}, {'cuota', 'servicio'})
        self.assertEqual(futuro['libre'], Decimal('590000'))

    def test_una_compra_en_cuotas_empieza_el_mes_siguiente(self):
        p = proyeccion(self.ana, compra={'monto': 60000, 'cuotas': 3})
        base = proyeccion(self.ana)
        self.assertEqual(p['meses'][0]['libre'], base['meses'][0]['libre'])
        for i in (1, 2, 3):
            self.assertEqual(p['meses'][i]['libre'], base['meses'][i]['libre'] - 20000)

    def test_una_compra_al_contado_baja_el_mes_actual_desde_hoy(self):
        p = proyeccion(self.ana, compra={'monto': 50000})
        base = proyeccion(self.ana)
        self.assertEqual(p['meses'][0]['libre'], base['meses'][0]['libre'] - 50000)
        self.assertEqual(p['dias'][0]['saldo'], base['dias'][0]['saldo'] - 50000)
        self.assertEqual(p['dias'][-1]['saldo'], base['dias'][-1]['saldo'] - 50000)

    def test_mas_cuotas_alargan_la_proyeccion(self):
        p = proyeccion(self.ana, compra={'monto': 60000, 'cuotas': 6})
        self.assertEqual(len(p['meses']), 7)

    def test_el_mes_mas_justo_es_el_de_menos_libre(self):
        p = proyeccion(self.ana)
        menor = min(p['meses'], key=lambda m: m['libre'])
        self.assertEqual(p['mas_justo'], menor['periodo'])
        self.assertEqual(p['alcanza'], all(m['libre'] >= 0 for m in p['meses']))

    def test_sin_datos_no_falla(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        p = proyeccion(beto)
        self.assertEqual(p['meses'][1]['libre'], Decimal('0'))
        self.assertTrue(p['dias'])
        self.assertIsInstance(p['dia_mas_justo'], date)
