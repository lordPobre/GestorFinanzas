from django.test import TestCase
from django.urls import reverse

from finanzas import legal


class PaginaSeguridadTests(TestCase):
    def _cuerpo(self, ruta):
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode('utf-8')

    def test_responde_y_marca_su_pestana(self):
        cuerpo = self._cuerpo(reverse('seguridad'))
        self.assertIn(f'href="{reverse("seguridad")}" aria-current="page"', cuerpo)
        self.assertNotIn(f'href="{reverse("privacidad")}" aria-current="page"', cuerpo)

    def test_muestra_notas_y_enlaces_a_los_informes(self):
        cuerpo = self._cuerpo(reverse('seguridad'))
        self.assertIn('A+', cuerpo)
        self.assertIn(legal.REVISION_SEGURIDAD, cuerpo)
        for url in (legal.INFORME_SSL_LABS, legal.INFORME_OBSERVATORY, legal.INFORME_INTERNET_NL):
            self.assertIn(url, cuerpo)

    def test_explica_como_reportar(self):
        cuerpo = self._cuerpo(reverse('seguridad'))
        self.assertIn(f'mailto:{legal.CORREO_CONTACTO}', cuerpo)
        self.assertIn(reverse('security_txt'), cuerpo)

    def test_secciones_con_ancla_y_titulo(self):
        cuerpo = self._cuerpo(reverse('seguridad'))
        self.assertEqual(cuerpo.count('<section id="'), 6)
        self.assertEqual(cuerpo.count('<h2>'), 6)

    def test_no_trae_scripts_sin_nonce(self):
        for trozo in self._cuerpo(reverse('seguridad')).split('<script')[1:]:
            self.assertIn('nonce=', trozo.split('>')[0])

    def test_security_txt_apunta_a_la_politica(self):
        cuerpo = self._cuerpo(reverse('security_txt'))
        self.assertIn('Policy: http://testserver/seguridad/', cuerpo)

    def test_la_landing_enlaza_la_pagina_y_los_informes(self):
        cuerpo = self._cuerpo(reverse('dashboard'))
        self.assertIn(f'href="{reverse("seguridad")}"', cuerpo)
        self.assertIn('ssllabs.com', cuerpo)
        self.assertIn('observatory', cuerpo)
