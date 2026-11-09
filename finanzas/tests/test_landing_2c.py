from django.test import TestCase
from django.urls import reverse

from finanzas import diseno


class Landing2cTests(TestCase):
    def test_sin_la_cookie_queda_la_landing_de_siempre(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('<html lang="es">', cuerpo)
        self.assertNotIn('css/landing-2c.css', cuerpo)
        self.assertIn('content="#ffaa2c"', cuerpo)

    def test_con_la_cookie_carga_la_piel_2c(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('<html lang="es" class="t2c">', cuerpo)
        self.assertIn('css/tema-2c.css', cuerpo)
        self.assertIn('css/landing-2c.css', cuerpo)
        self.assertIn('content="#F3EFE7"', cuerpo)
        self.assertIn('class="lp-nav-crear"', cuerpo)
        self.assertIn('aria-controls="lp-panel-cuotas"', cuerpo)
