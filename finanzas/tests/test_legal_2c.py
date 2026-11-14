from django.test import TestCase
from django.urls import reverse

from finanzas.tests.test_csp_estilos import ATRIBUTO_STYLE

PAGINAS = ('privacidad', 'terminos', 'seguridad')


class Legal2cTests(TestCase):
    def test_usan_el_diseno_nuevo(self):
        for nombre in PAGINAS:
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)
                self.assertTemplateUsed(respuesta, 'finanzas/legal_base_2c.html')
                self.assertTemplateNotUsed(respuesta, 'finanzas/legal_base.html')
                cuerpo = respuesta.content.decode('utf-8')
                self.assertIn('<html lang="es" class="t2c f2c">', cuerpo)
                self.assertIn('css/legal-2c.css', cuerpo)
                self.assertNotIn('css/finapp.css', cuerpo)
                self.assertIn('aria-current="page"', cuerpo)
                self.assertIn('class="legal-cuerpo"', cuerpo)
                self.assertIn('data-legal-indice', cuerpo)
                self.assertIsNone(ATRIBUTO_STYLE.search(cuerpo))
