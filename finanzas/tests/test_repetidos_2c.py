from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas import diseno
from finanzas.models import Transaccion

SW = Path(settings.BASE_DIR) / 'static' / 'js' / 'sw.js'


class Repetidos2cTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.client.cookies[diseno.COOKIE] = diseno.VALOR

    def gasto(self, fecha, desc, monto='23450'):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                          categoria='Comida', fecha=fecha, descripcion=desc)

    def test_usa_la_plantilla_2c_sin_la_hoja_vieja(self):
        self.gasto(date(2026, 9, 14), 'LIDER EXPRESS')
        self.gasto(date(2026, 9, 14), 'Lider Express')
        r = self.client.get(reverse('movimientos_repetidos'))
        self.assertTemplateUsed(r, 'finanzas/repetidos_2c.html')
        cuerpo = r.content.decode('utf-8')
        self.assertIn('css/repetidos-2c.css', cuerpo)
        self.assertNotIn('css/repetidos.css', cuerpo)
        self.assertEqual(cuerpo.count('class="rp2c-par"'), 1)
        self.assertIn('Borrar 1 repetida', cuerpo)
        self.assertIn('Misma descripción', cuerpo)
        self.assertEqual(r.context['total_marcado'], Decimal('23450'))

    def test_sin_repetidos_muestra_el_vacio(self):
        r = self.client.get(reverse('movimientos_repetidos'))
        self.assertContains(r, 'No hay movimientos repetidos')
        self.assertNotContains(r, 'rp2c-resumen')

    def test_sin_la_cookie_sigue_la_pantalla_de_siempre(self):
        del self.client.cookies[diseno.COOKIE]
        r = self.client.get(reverse('movimientos_repetidos'))
        self.assertTemplateUsed(r, 'finanzas/repetidos.html')
        self.assertTemplateNotUsed(r, 'finanzas/repetidos_2c.html')


class SinConexion2cTests(SimpleTestCase):

    def test_la_pagina_sin_conexion_usa_el_papel_crema(self):
        texto = SW.read_text('utf-8')
        self.assertIn('background:#F3EFE7', texto)
        self.assertNotIn('#191919', texto)
        self.assertNotIn('Manrope', texto)
