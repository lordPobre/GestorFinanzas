from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas import diseno
from finanzas.templatetags import f2c


def plan_de_prueba():
    deudas = [{'nombre': 'Tienda', 'saldo': Decimal('200000'), 'cuota': Decimal('50000')}]
    return {
        'tiene_datos': True, 'sobra': Decimal('500000'), 'falta': Decimal('0'),
        'ingreso': Decimal('900000'), 'gasto': Decimal('300000'), 'compromisos': Decimal('100000'),
        'tope_mes': Decimal('500000'), 'limitado': False, 'meses_base': 3, 'pocos_datos': False,
        'deudas': deudas, 'meta': Decimal('1200000'), 'llevas': Decimal('300000'), 'tiene_fondo': True,
        'suscripciones': [],
        'datos': {'sobra': 500000, 'meta': 1200000, 'llevas': 300000,
                  'deudas': [{'nombre': 'Tienda', 'saldo': 200000, 'cuota': 50000}],
                  'ahorro': 200000, 'extra': 150000, 'anio': 2026, 'mes': 11},
    }


class BarrasMesTests(SimpleTestCase):
    def test_terminan_en_el_mes_elegido_con_meses_cortos(self):
        meses = ['junio 2026', 'julio 2026', 'agosto 2026', 'septiembre 2026', 'octubre 2026', 'noviembre 2026']
        barras = f2c.barras(meses, [1, 2, 3, 4, 5, 6], 3, 'Octubre 2026')
        self.assertEqual([b['etiqueta'] for b in barras], ['agosto 2026', 'septiembre 2026', 'octubre 2026'])
        self.assertEqual([b['corta'] for b in barras], ['Ago', 'Sep', 'Oct'])
        self.assertEqual([b['anio'] for b in barras], ['2026', '', ''])
        self.assertTrue(barras[-1]['actual'])

    def test_el_anio_aparece_cuando_cambia(self):
        barras = f2c.barras(['diciembre 2025', 'enero 2026'], [1, 1], 6)
        self.assertEqual([b['anio'] for b in barras], ['2025', '2026'])

    def test_sin_mes_elegido_o_sin_coincidencia_quedan_los_ultimos(self):
        meses = ['junio 2026', 'julio 2026', 'agosto 2026']
        self.assertEqual([b['corta'] for b in f2c.barras(meses, [1, 2, 3], 2)], ['Jul', 'Ago'])
        self.assertEqual([b['corta'] for b in f2c.barras(meses, [1, 2, 3], 2, 'Marzo 2020')], ['Jul', 'Ago'])


class TuPlanEscritorioTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.client.cookies[diseno.COOKIE] = diseno.VALOR

    def test_trae_la_cuenta_la_ruta_y_las_herramientas(self):
        with mock.patch('finanzas.views.plan.armar_plan', return_value=plan_de_prueba()):
            cuerpo = self.client.get(reverse('plan_plata')).content.decode('utf-8')
        for pieza in ('class="pl2c-cuenta pl2c-pc"', 'class="pl2c-ruta-cab pl2c-pc"', 'Prueba tu plan',
                      'data-herr-ir="sim"', 'data-herr-ir="fondo"', 'data-herr-ir="deudas"', 'data-herr-ir="dap"',
                      'data-herr-panel="sim"', 'data-herr-panel="fondo"', 'data-herr-panel="deudas"',
                      'data-herr-panel="dap"', 'data-ancho-pct="25"'):
            self.assertIn(pieza, cuerpo)

    def test_sin_cuotas_no_ofrece_la_herramienta_de_cuotas(self):
        plan = plan_de_prueba()
        plan['deudas'] = []
        plan['datos']['deudas'] = []
        with mock.patch('finanzas.views.plan.armar_plan', return_value=plan):
            cuerpo = self.client.get(reverse('plan_plata')).content.decode('utf-8')
        self.assertNotIn('data-herr-ir="deudas"', cuerpo)
        self.assertNotIn('data-herr-panel="deudas"', cuerpo)

    def test_estadisticas_marca_el_mes_elegido(self):
        cuerpo = self.client.get(reverse('estadisticas')).content.decode('utf-8')
        self.assertIn('class="es2c-barra actual"', cuerpo)
        self.assertNotIn('<small>junio 2026</small>', cuerpo)
