import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas import diseno

HOJA_2C = Path(settings.BASE_DIR) / 'static' / 'css' / 'tema-2c.css'
FUENTES = Path(settings.BASE_DIR) / 'static' / 'vendor' / 'fonts'


class Diseno2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _cuerpo(self):
        return self.client.get(reverse('por_pagar')).content.decode('utf-8')

    def test_sin_la_cookie_queda_el_diseno_actual(self):
        cuerpo = self._cuerpo()
        self.assertIn('<html lang="es">', cuerpo)
        self.assertNotIn('css/tema-2c.css', cuerpo)
        self.assertIn('content="#151412"', cuerpo)
        self.assertNotIn(reverse('diseno_actual'), cuerpo)

    def test_con_la_cookie_carga_el_tema_2c(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        cuerpo = self._cuerpo()
        self.assertIn('<html lang="es" class="t2c">', cuerpo)
        self.assertIn('css/tema-2c.css', cuerpo)
        self.assertIn('content="#F3EFE7"', cuerpo)
        self.assertEqual(cuerpo.count(f'href="{reverse("diseno_actual")}"'), 2)

    def test_otro_valor_de_la_cookie_no_cuenta(self):
        self.client.cookies[diseno.COOKIE] = 'otro'
        self.assertNotIn('css/tema-2c.css', self._cuerpo())

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


class HojaDelTema2cTests(SimpleTestCase):
    def test_cada_regla_va_bajo_t2c(self):
        selectores = []
        for linea in HOJA_2C.read_text('utf-8').splitlines():
            linea = linea.strip()
            if not linea.endswith('{') and '{' not in linea:
                continue
            cabeza = linea.split('{', 1)[0].strip()
            if not cabeza or cabeza.startswith('@'):
                continue
            selectores.extend(s.strip() for s in cabeza.split(','))
        self.assertTrue(selectores)
        for s in selectores:
            with self.subTest(selector=s):
                self.assertTrue(s.startswith('html.t2c'))

    def test_no_toca_la_franja_de_la_barra_de_estado(self):
        texto = HOJA_2C.read_text('utf-8')
        self.assertNotIn('::after { opacity', texto)
        self.assertIsNone(re.search(r'body:not\(:has\(\.auth\)\)::after', texto))

    def test_la_letra_nueva_esta_en_las_fuentes(self):
        self.assertIn("font-family: 'Familjen Grotesk';", (FUENTES / 'fuentes.css').read_text('utf-8'))
        self.assertTrue((FUENTES / 'familjen-grotesk-wght.ttf').exists())
