import json
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

REGLAS = re.compile(r'<script type="speculationrules" nonce="([^"]+)">(.*?)</script>', re.S)


class PrecargaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _reglas(self, nombre):
        respuesta = self.client.get(reverse(nombre))
        encontradas = REGLAS.findall(respuesta.content.decode())
        self.assertEqual(len(encontradas), 1)
        nonce, cuerpo = encontradas[0]
        return respuesta, nonce, json.loads(cuerpo)

    def test_las_pantallas_con_sesion_traen_las_reglas_con_el_nonce(self):
        for nombre in ('dashboard', 'deudas', 'metas'):
            with self.subTest(pantalla=nombre):
                respuesta, nonce, _ = self._reglas(nombre)
                self.assertIn(f"'nonce-{nonce}'", respuesta['Content-Security-Policy'])

    def test_solo_precarga_y_nunca_prerenderiza(self):
        _, _, reglas = self._reglas('dashboard')
        self.assertEqual(list(reglas), ['prefetch'])
        self.assertEqual(reglas['prefetch'][0]['eagerness'], 'moderate')

    def test_solo_los_menus_y_sin_cartola(self):
        _, _, reglas = self._reglas('dashboard')
        condiciones = json.dumps(reglas['prefetch'][0]['where'])
        self.assertIn('.sidebar-nav a[href]', condiciones)
        self.assertIn('.bottomnav a[href]', condiciones)
        self.assertIn('/cartola/*', condiciones)
