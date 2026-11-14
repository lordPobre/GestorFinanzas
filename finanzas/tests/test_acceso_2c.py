from django.test import TestCase
from django.urls import reverse

from finanzas import plantillas_2c
from finanzas.tests.test_csp_estilos import ATRIBUTO_STYLE

PAGINAS = ('registro', 'recuperar')


class Acceso2cTests(TestCase):
    def test_la_base_de_acceso_tiene_version_2c(self):
        self.assertEqual(plantillas_2c.plantilla('registration/auth_base.html'), 'registration/auth_base_2c.html')

    def test_usan_la_base_2c(self):
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)
                self.assertTemplateUsed(respuesta, 'registration/auth_base_2c.html')
                self.assertTemplateNotUsed(respuesta, 'registration/auth_base.html')
                cuerpo = respuesta.content.decode('utf-8')
                self.assertIn('<html lang="es" class="t2c f2c">', cuerpo)
                self.assertIn('class="ac2c ac2c-pag"', cuerpo)
                self.assertIn('css/acceso-2c.css', cuerpo)
                self.assertIn('css/franja-2c.css', cuerpo)
                self.assertNotIn('css/finapp.css', cuerpo)
                self.assertIn('name="apple-mobile-web-app-status-bar-style" content="black-translucent"', cuerpo)
                self.assertIsNone(ATRIBUTO_STYLE.search(cuerpo))

    def test_el_registro_trae_todo_el_formulario(self):
        cuerpo = self.client.get(reverse('registro')).content.decode('utf-8')
        for pieza in ('Crea tu cuenta', 'name="email_perfil"', 'name="password1"', 'name="password2"',
                      'name="acepta_politica"', 'id="fuerzaBar"', 'js/pantallas/registro.js', 'class="ac2c-docs"'):
            self.assertIn(pieza, cuerpo)
