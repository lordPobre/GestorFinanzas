import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

HOJA = Path(settings.BASE_DIR) / 'static' / 'css' / 'transiciones.css'
TITULO = re.compile(r'class="sec-titulo[ "]')
CIFRA = re.compile(r'class="sec-monto[ "]')
PANTALLAS = ('dashboard', 'por_pagar', 'deudas', 'suscripciones', 'metas', 'prestamos',
             'estadisticas', 'categorias', 'perfil')


class HojaTransicionesTests(SimpleTestCase):

    def test_va_en_la_capa_app_y_nombra_lo_que_viaja(self):
        css = HOJA.read_text(encoding='utf-8')
        self.assertTrue(css.startswith('@layer app {'))
        for nombre in ('titulo', 'cifra', 'esfera'):
            self.assertIn(f'view-transition-name: {nombre};', css)

    def test_en_inicio_la_esfera_de_la_barra_no_compite_con_la_grande(self):
        css = HOJA.read_text(encoding='utf-8')
        self.assertIn('body:not(:has(.ini-esfera)) .sidebar-foot.health .salud-esfera', css)
        self.assertIn('.ini-valor:not([hidden]) > .ini-monto', css)


class NombresUnicosTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_cada_pantalla_tiene_a_lo_mas_un_titulo_y_una_cifra(self):
        for nombre in PANTALLAS:
            with self.subTest(pantalla=nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertIn('css/transiciones.css', html)
                self.assertLessEqual(len(TITULO.findall(html)), 1)
                self.assertLessEqual(len(CIFRA.findall(html)), 1)
