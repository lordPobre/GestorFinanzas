from django.test import TestCase
from django.urls import reverse

from finanzas import diseno


class Landing2cTests(TestCase):
    def test_sin_la_cookie_queda_la_landing_de_siempre(self):
        respuesta = self.client.get(reverse('dashboard'))
        cuerpo = respuesta.content.decode('utf-8')
        self.assertTemplateUsed(respuesta, 'finanzas/landing.html')
        self.assertIn('<html lang="es">', cuerpo)
        self.assertNotIn('css/landing-2c.css', cuerpo)
        self.assertIn('content="#ffaa2c"', cuerpo)

    def test_con_la_cookie_trae_la_landing_del_prototipo(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        respuesta = self.client.get(reverse('dashboard'))
        cuerpo = respuesta.content.decode('utf-8')
        self.assertTemplateUsed(respuesta, 'finanzas/landing_2c.html')
        self.assertIn('<html lang="es" class="t2c f2c">', cuerpo)
        self.assertIn('css/landing-2c.css', cuerpo)
        self.assertNotIn('css/finapp.css', cuerpo)
        self.assertNotIn('tema-2c', cuerpo)
        self.assertIn('content="#F3EFE7"', cuerpo)
        self.assertIn('Cuánto puedes gastar, sin planilla.', cuerpo)
        self.assertIn('aria-controls="l2c-panel-cuotas"', cuerpo)
        self.assertIn('data-lp-chat-form', cuerpo)
        self.assertIn('application/ld+json', cuerpo)
        self.assertIn(f'href="{reverse("registro")}"', cuerpo)


class Entrar2cTests(TestCase):
    def test_sin_la_cookie_queda_la_entrada_de_siempre(self):
        respuesta = self.client.get(reverse('login'))
        self.assertTemplateUsed(respuesta, 'registration/login.html')
        self.assertNotContains(respuesta, 'css/acceso-2c.css')

    def test_con_la_cookie_trae_la_entrada_del_prototipo(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        respuesta = self.client.get(reverse('login'))
        self.assertTemplateUsed(respuesta, 'registration/login_2c.html')
        for pieza in ('css/acceso-2c.css', 'Entra a tu cuenta', 'id="btnPasskey"', 'id="btnEntrar"',
                      'name="username"', 'name="password"', 'data-ver-pass', 'js/pantallas/login.js'):
            self.assertContains(respuesta, pieza)
        self.assertNotContains(respuesta, 'css/finapp.css')

    def test_con_la_cookie_se_puede_entrar(self):
        from django.contrib.auth.models import User
        User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        respuesta = self.client.post(reverse('login'), {'username': 'ana', 'password': 'clave-larga-1'})
        self.assertEqual(respuesta.status_code, 302)
