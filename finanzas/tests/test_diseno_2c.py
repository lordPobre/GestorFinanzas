import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from finanzas import diseno

HOJA_2C = Path(settings.BASE_DIR) / 'static' / 'css' / 'fintora-2c.css'
FUENTES = Path(settings.BASE_DIR) / 'static' / 'vendor' / 'fonts'


class Diseno2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _cuerpo(self):
        return self.client.get(reverse('metas')).content.decode('utf-8')

    def test_sin_la_cookie_queda_el_diseno_actual(self):
        cuerpo = self._cuerpo()
        self.assertIn('<html lang="es">', cuerpo)
        self.assertNotIn('css/fintora-2c.css', cuerpo)
        self.assertIn('content="#151412"', cuerpo)
        self.assertNotIn(reverse('diseno_actual'), cuerpo)

    def test_con_la_cookie_carga_la_base_2c(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        cuerpo = self._cuerpo()
        self.assertIn('<html lang="es" class="t2c f2c">', cuerpo)
        self.assertIn('css/fintora-2c.css', cuerpo)
        self.assertNotIn('css/finapp.css', cuerpo)
        self.assertIn('content="#F3EFE7"', cuerpo)
        self.assertNotIn(reverse('diseno_actual'), cuerpo)
        self.assertNotIn('Volver al diseño actual', cuerpo)

    def test_otro_valor_de_la_cookie_no_cuenta(self):
        self.client.cookies[diseno.COOKIE] = 'otro'
        self.assertNotIn('css/fintora-2c.css', self._cuerpo())

    def test_probar_deja_la_cookie_y_vuelve_al_inicio(self):
        respuesta = self.client.get(reverse('diseno_2c'))
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)
        galleta = respuesta.cookies[diseno.COOKIE]
        self.assertEqual(galleta.value, diseno.VALOR)
        self.assertTrue(galleta['httponly'])
        self.assertEqual(galleta['samesite'], 'Lax')

    def test_volver_borra_la_cookie(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        respuesta = self.client.get(reverse('diseno_actual'))
        self.assertEqual(respuesta.cookies[diseno.COOKIE].value, '')

    def test_next_propio_se_sigue(self):
        respuesta = self.client.get(reverse('diseno_2c') + '?next=' + reverse('deudas'))
        self.assertRedirects(respuesta, reverse('deudas'), fetch_redirect_response=False)

    def test_next_de_otro_sitio_no_se_sigue(self):
        respuesta = self.client.get(reverse('diseno_2c') + '?next=https://otro.cl/')
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)


@override_settings(DISENO_2C_PARA_TODOS=True)
class Diseno2cParaTodosTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_sin_cookie_se_ve_el_2c(self):
        self.assertContains(self.client.get(reverse('metas')), 'css/fintora-2c.css')

    def test_volver_deja_la_cookie_del_diseno_actual(self):
        respuesta = self.client.get(reverse('diseno_actual'))
        self.assertEqual(respuesta.cookies[diseno.COOKIE].value, diseno.ACTUAL)
        self.client.cookies[diseno.COOKIE] = diseno.ACTUAL
        self.assertNotContains(self.client.get(reverse('metas')), 'css/fintora-2c.css')

    def test_probar_borra_la_cookie_del_diseno_actual(self):
        self.client.cookies[diseno.COOKIE] = diseno.ACTUAL
        respuesta = self.client.get(reverse('diseno_2c'))
        self.assertEqual(respuesta.cookies[diseno.COOKIE].value, '')


class HojaDelDiseno2cTests(SimpleTestCase):
    def test_las_pieles_viejas_ya_no_estan(self):
        css = Path(settings.BASE_DIR) / 'static' / 'css'
        self.assertFalse((css / 'tema-2c.css').exists())
        self.assertFalse((css / 'tema-2c-auto.css').exists())

    def test_no_toca_la_franja_de_la_barra_de_estado(self):
        texto = HOJA_2C.read_text('utf-8')
        self.assertNotIn('con-scroll', texto)
        self.assertIsNone(re.search(r'body:not\(:has\(\.auth\)\)::after', texto))

    def test_la_letra_nueva_esta_en_las_fuentes(self):
        self.assertIn("font-family: 'Familjen Grotesk';", (FUENTES / 'fuentes.css').read_text('utf-8'))
        self.assertTrue((FUENTES / 'familjen-grotesk-wght.ttf').exists())
