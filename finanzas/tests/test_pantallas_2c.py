from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas import diseno, plantillas_2c
from finanzas.templatetags import f2c


class Cargador2cTests(SimpleTestCase):
    def test_sin_el_2c_no_cambia_el_nombre(self):
        self.assertEqual(plantillas_2c.plantilla('finanzas/metas.html'), 'finanzas/metas.html')

    def test_con_el_2c_cambia_solo_las_que_tienen_version(self):
        marca = plantillas_2c._activo.set(True)
        try:
            self.assertEqual(plantillas_2c.plantilla('finanzas/metas.html'), 'finanzas/metas_2c.html')
            self.assertEqual(plantillas_2c.plantilla('finanzas/base.html'), 'finanzas/base_2c.html')
            self.assertEqual(plantillas_2c.plantilla('registration/login.html'), 'registration/login_2c.html')
            self.assertEqual(plantillas_2c.plantilla('finanzas/correo_pagos.html'), 'finanzas/correo_pagos.html')
        finally:
            plantillas_2c._activo.reset(marca)

    def test_cada_version_2c_existe(self):
        from django.template.loader import get_template
        for nueva in plantillas_2c.PLANTILLAS.values():
            with self.subTest(plantilla=nueva):
                self.assertTrue(get_template(nueva))


class Filtros2cTests(SimpleTestCase):
    def test_pasados_deja_fuera_lo_que_falta_pagar_y_lo_futuro(self):
        hoy = date(2026, 11, 9)
        items = [
            SimpleNamespace(nombre='a', fecha=hoy, por_pagar=False),
            SimpleNamespace(nombre='b', fecha=hoy, por_pagar=True),
            SimpleNamespace(nombre='c', fecha=hoy + timedelta(days=3), por_pagar=False),
            SimpleNamespace(nombre='d', fecha=hoy - timedelta(days=1), por_pagar=False),
        ]
        with mock.patch('finanzas.templatetags.f2c.fechas.hoy', return_value=hoy):
            self.assertEqual([t.nombre for t in f2c.pasados(items, 5)], ['a', 'd'])
            self.assertEqual(len(f2c.pasados(items, 1)), 1)

    def test_corto(self):
        self.assertEqual(f2c.corto(Decimal('9500'), '$'), '$9.500')
        self.assertEqual(f2c.corto(Decimal('120400'), '$'), '$120 mil')
        self.assertEqual(f2c.corto(Decimal('1250000'), '$'), '$1,2 M')

    def test_barras_toma_los_ultimos_meses_y_marca_el_actual(self):
        barras = f2c.barras(['jun', 'jul', 'ago'], [100, 0, 50], 2)
        self.assertEqual([b['etiqueta'] for b in barras], ['jul', 'ago'])
        self.assertEqual(barras[-1]['alto'], 100)
        self.assertTrue(barras[-1]['actual'])
        self.assertEqual(barras[0]['alto'], 4)

    def test_tope_pct(self):
        self.assertEqual(f2c.tope_pct(30, 75), 40)
        self.assertEqual(f2c.tope_pct(30, 0), 0)
        self.assertEqual(f2c.tope_pct(200, 100), 100)


class Pantallas2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.client.cookies[diseno.COOKIE] = diseno.VALOR

    def test_inicio_avisa_que_falta_el_ingreso_y_explica_como_sigue_tu_plata(self):
        response = self.client.get(reverse('dashboard'))
        cuerpo = response.content.decode('utf-8')
        self.assertIn('Falta tu ingreso de', cuerpo)
        self.assertIn('Sin el sueldo, la cifra solo resta lo que gastas y pagas.', cuerpo)
        self.assertIn('Cómo sigue tu plata', cuerpo)
        self.assertIn('La línea es la plata que te va quedando cada día si sigues gastando como siempre', cuerpo)

    def test_el_panel_para_anotar_trae_cuotas_y_cartola(self):
        cuerpo = self.client.get(reverse('metas')).content.decode('utf-8')
        self.assertIn('class="anotar-atajos"', cuerpo)
        self.assertIn(f'href="{reverse("crear_deuda")}"', cuerpo)
        self.assertIn(f'href="{reverse("importar_cartola")}"', cuerpo)

    def test_los_formularios_sueltos_van_en_la_base_2c(self):
        for nombre in ('crear_deuda', 'crear_meta', 'registrar_transaccion'):
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre), follow=True)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTemplateUsed(respuesta, 'finanzas/base_2c.html')
                self.assertNotContains(respuesta, 'css/finapp.css')

    def test_estadisticas_dibuja_las_barras_sin_chart(self):
        respuesta = self.client.get(reverse('estadisticas'))
        self.assertContains(respuesta, 'class="es2c-barras"')
        self.assertNotContains(respuesta, 'chart.umd.min.js')

    def test_tu_trae_la_lista_del_prototipo(self):
        respuesta = self.client.get(reverse('perfil'))
        for pieza in ('Categorías y topes', 'Importar cartola', 'Anotar desde Telegram', 'Análisis con IA',
                      'id="formPerfil"', 'id="vistaAvatar"', 'Eliminar mi cuenta'):
            self.assertContains(respuesta, pieza)
