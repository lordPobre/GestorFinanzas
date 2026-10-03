from django.test import TestCase
from django.urls import reverse


class LandingDisenoTests(TestCase):
    def setUp(self):
        self.cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')

    def test_el_menu_ofrece_crear_cuenta(self):
        self.assertIn('class="lp-nav-crear"', self.cuerpo)
        self.assertIn('class="lp-nav-entrar"', self.cuerpo)

    def test_las_pestanas_apuntan_a_su_panel(self):
        for nombre in ('cuotas', 'cartola', 'deben', 'subs'):
            self.assertIn(f'aria-controls="lp-panel-{nombre}"', self.cuerpo)
            self.assertIn(f'id="lp-panel-{nombre}"', self.cuerpo)

    def test_los_ejemplos_no_usan_zoom_ni_ancho_fijo(self):
        self.assertNotIn('width:520px', self.cuerpo)
        self.assertNotIn('width:460px', self.cuerpo)

    def test_no_quedan_enlaces_vacios(self):
        self.assertNotIn('href="#" target="_blank"', self.cuerpo)
