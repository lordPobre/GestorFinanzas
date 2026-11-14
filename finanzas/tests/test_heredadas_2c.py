import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


HOJA = Path(settings.BASE_DIR) / 'static' / 'css' / 'heredadas-2c.css'
BASE = Path(settings.BASE_DIR) / 'finanzas' / 'templates' / 'finanzas' / 'base_2c.html'
PANTALLAS = ('metas', 'encuesta', 'sesiones_activas', 'actividad_cuenta', 'crear_deuda')
PARENTESIS = re.compile(r'\([^()]*\)')


class Heredadas2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_las_pantallas_cargan_la_hoja(self):
        for nombre in PANTALLAS:
            with self.subTest(pantalla=nombre):
                html = self.client.get(reverse(nombre), follow=True).content.decode('utf-8')
                self.assertIn('css/heredadas-2c.css', html)

class HojaHeredadasTests(SimpleTestCase):
    def test_cada_regla_vale_solo_con_el_2c(self):
        for linea in HOJA.read_text('utf-8').splitlines():
            linea = linea.strip()
            if not linea or linea.startswith(('@', '}')) or '{' not in linea:
                continue
            selector = linea.split('{', 1)[0]
            while PARENTESIS.search(selector):
                selector = PARENTESIS.sub('', selector)
            for parte in selector.split(','):
                with self.subTest(selector=parte.strip()):
                    self.assertTrue(parte.strip().startswith(('html.f2c', ':where')))

    def test_los_avisos_muestran_la_plata_con_separador(self):
        self.assertNotIn('floatformat:0', BASE.read_text('utf-8'))
