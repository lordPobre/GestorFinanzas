from django.test import TestCase
from django.urls import reverse

from finanzas import legal


class PaginasLegalesTests(TestCase):
    def _cuerpo(self, nombre):
        respuesta = self.client.get(reverse(nombre))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode('utf-8')

    def test_cada_pagina_marca_su_pestana(self):
        for nombre, otra in (('privacidad', 'terminos'), ('terminos', 'privacidad')):
            with self.subTest(pagina=nombre):
                cuerpo = self._cuerpo(nombre)
                self.assertIn(f'href="{reverse(nombre)}" aria-current="page"', cuerpo)
                self.assertNotIn(f'href="{reverse(otra)}" aria-current="page"', cuerpo)

    def test_muestran_version_y_contacto(self):
        for nombre in ('privacidad', 'terminos'):
            with self.subTest(pagina=nombre):
                cuerpo = self._cuerpo(nombre)
                self.assertIn(legal.VERSION, cuerpo)
                self.assertIn(legal.VIGENTE_DESDE, cuerpo)
                self.assertIn(f'mailto:{legal.CORREO_CONTACTO}', cuerpo)

    def test_las_secciones_tienen_ancla_y_titulo(self):
        for nombre, cantidad in (('privacidad', 15), ('terminos', 10)):
            with self.subTest(pagina=nombre):
                cuerpo = self._cuerpo(nombre)
                self.assertEqual(cuerpo.count('<section id="'), cantidad)
                self.assertEqual(cuerpo.count('<h2>'), cantidad)

    def test_no_traen_scripts_sin_nonce(self):
        for nombre in ('privacidad', 'terminos'):
            with self.subTest(pagina=nombre):
                for trozo in self._cuerpo(nombre).split('<script')[1:]:
                    self.assertIn('nonce=', trozo.split('>')[0])
