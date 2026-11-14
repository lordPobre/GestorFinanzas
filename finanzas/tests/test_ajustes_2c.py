from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from finanzas.models import Transaccion
from finanzas.servicios import vida_2c
from finanzas.tests.test_vistas import BaseDosUsuarios

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates' / 'finanzas'


class FlujoTests(SimpleTestCase):
    def test_si_sale_mas_de_lo_que_entra_la_barra_no_se_pasa(self):
        r = vida_2c.flujo(Decimal('1000'), Decimal('1210'), Decimal('30'))
        self.assertAlmostEqual(float(r['gasto']) + float(r['cuotas']), 100, places=1)
        self.assertTrue(r['pasa'])
        self.assertIsNone(r['sobra'])
        self.assertIsNotNone(r['marca'])
        self.assertEqual(int(r['pct_gasto']), 121)
        self.assertEqual(int(r['pct_cuotas']), 3)

    def test_si_sobra_se_reparte_lo_que_entra(self):
        r = vida_2c.flujo(Decimal('1000'), Decimal('600'), Decimal('100'))
        self.assertFalse(r['pasa'])
        self.assertIsNone(r['marca'])
        self.assertEqual(int(r['pct_sobra']), 30)
        self.assertAlmostEqual(float(r['gasto']) + float(r['cuotas']) + float(r['sobra']), 100, places=1)

    def test_sin_ingreso_no_hay_barra(self):
        self.assertIsNone(vida_2c.flujo(Decimal('0'), Decimal('500'), Decimal('0')))


class EscalaTests(SimpleTestCase):
    def test_las_barras_traen_lineas_y_montos(self):
        r = vida_2c.barras_dobles(['octubre 2026', 'noviembre 2026'], [3000000, 100], [100, 2800000], 6,
                                  'noviembre 2026', date(2026, 11, 12))
        self.assertEqual(len(r['escala']), 2)
        self.assertGreaterEqual(r['escala'][0]['valor'], 3000000)
        self.assertLess(float(r['meses'][0]['ent']), 100)
        self.assertEqual(r['meses'][1]['sal_valor'], Decimal('2800000'))


class CuotasPlegablesTests(SimpleTestCase):
    def test_las_compras_pagadas_se_pueden_esconder(self):
        texto = (PLANTILLAS / 'deudas_2c.html').read_text('utf-8')
        self.assertIn('<details class="c2c-tarjeta c2c-saldadas">', texto)
        self.assertIn('<summary class="c2c-saldadas-cab">', texto)


class Formularios2cTests(BaseDosUsuarios):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.ana)

    def test_editar_movimiento_usa_la_hoja_de_editar_compra(self):
        gasto = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                           categoria='Comida', fecha=date.today())
        respuesta = self.client.get(reverse('editar_transaccion', args=[gasto.pk]))
        self.assertContains(respuesta, 'class="fo2c-hoja"')
        self.assertContains(respuesta, 'id="segTipoMov"')
        self.assertContains(respuesta, 'css/formularios-2c.css')

    def test_las_suscripciones_usan_la_misma_hoja(self):
        for ruta in (reverse('editar_suscripcion', args=[self.de_ana['sub'].pk]), reverse('crear_suscripcion')):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertContains(respuesta, 'class="fo2c-hoja"')
                self.assertContains(respuesta, 'id="subAnual"')

    def test_editar_se_abre_en_una_ventana_flotante(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('js/pantallas/editar-flotante.js', cuerpo)
        self.assertIn('data-js="editar-flotante"', cuerpo)
        self.assertIn('css/formularios-2c.css', cuerpo)
