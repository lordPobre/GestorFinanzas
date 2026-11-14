from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno, navegacion


def _trozo(html, desde, hasta):
    i = html.index(desde)
    return html[i:html.index(hasta, i)]


class Navegacion2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _html(self, nombre, con_2c=True):
        if con_2c:
            self.client.cookies[diseno.COOKIE] = diseno.VALOR
        return self.client.get(reverse(nombre), follow=True).content.decode('utf-8')

    def test_la_barra_lateral_tiene_las_cuatro_secciones(self):
        lateral = _trozo(self._html('deudas'), 'class="sidebar-nav"', '</nav>')
        for etiqueta in ('Inicio', 'Pagos', 'Plan', 'Tú'):
            self.assertIn(f'data-label="{etiqueta}"', lateral)
        self.assertIn(f'href="{reverse("por_pagar")}" data-label="Pagos" class="nav-item active" aria-current="page"', lateral)
        self.assertEqual(lateral.count('aria-current="page"'), 1)
        self.assertNotIn('nav-title', lateral)

    def test_la_barra_de_abajo_trae_anotar_al_centro_y_no_mas(self):
        html = self._html('metas')
        barra = _trozo(html, 'class="bottomnav barra-2c"', '</nav>')
        self.assertLess(barra.index('data-label="Pagos"'), barra.index('data-label="Anotar"'))
        self.assertLess(barra.index('data-label="Anotar"'), barra.index('data-label="Plan"'))
        self.assertIn('data-open="#modalGasto"', barra)
        self.assertNotIn('data-label="Más"', barra)
        self.assertNotIn('class="fab-group"', html)

    def test_plan_trae_sus_pestanas(self):
        pestanas = _trozo(self._html('estadisticas'), 'class="sec-2c-pestanas"', '</nav>')
        for nombre in ('metas', 'plan_plata', 'analisis_predictivo'):
            self.assertIn(f'href="{reverse(nombre)}"', pestanas)
        self.assertIn('aria-current="page">Estadísticas</a>', pestanas)

    def test_tu_trae_sus_pestanas_sin_la_vuelta_al_diseno_actual(self):
        pestanas = _trozo(self._html('categorias'), 'class="sec-2c-pestanas"', '</nav>')
        self.assertIn('aria-current="page">Categorías y topes</a>', pestanas)
        self.assertNotIn(reverse('diseno_actual'), pestanas)

    def test_las_pantallas_de_pagos_no_repiten_pestanas(self):
        self.assertNotIn('class="sec-2c-pestanas"', self._html('por_pagar'))

    def test_sin_la_cookie_queda_la_navegacion_de_siempre(self):
        html = self._html('metas', con_2c=False)
        self.assertIn('class="fab-group"', html)
        self.assertIn('data-label="Más"', html)
        self.assertNotIn('barra-2c', html)
        self.assertNotIn('sec-2c-pestanas', html)

    def test_cada_pantalla_de_una_seccion_cae_en_ella(self):
        self.assertEqual(navegacion.seccion_2c('revisar_cartola'), 'tu')
        self.assertEqual(navegacion.seccion_2c('editar_deuda'), 'pagos')
        self.assertEqual(navegacion.seccion_2c('plan_plata'), 'plan')
        self.assertIsNone(navegacion.seccion_2c('otra'))
