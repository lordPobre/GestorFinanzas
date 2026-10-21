import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates'
CAPAS = Path(settings.BASE_DIR) / 'static' / 'css' / 'capas.css'
HOJA = re.compile(r'<link rel="stylesheet" href="\{% static \'([^\']+)\' %\}">')
CON_CAPAS = (
    'finanzas/base.html',
    'registration/auth_base.html',
    'finanzas/landing.html',
    'finanzas/legal_base.html',
    'finanzas/onboarding.html',
)
DE_TERCEROS = ('vendor/fonts/fuentes.css', 'vendor/fontawesome/css/all.min.css')


class CapasDeCascadaTests(SimpleTestCase):

    def test_el_orden_de_las_capas_se_declara_primero(self):
        primera = CAPAS.read_text('utf-8').strip().splitlines()[0]
        self.assertEqual(primera, '@layer vendor, base, tema, pantallas, ajustes;')

    def test_lo_de_terceros_entra_en_su_capa(self):
        texto = CAPAS.read_text('utf-8')
        for hoja in DE_TERCEROS:
            nombre = hoja.split('/', 1)[1]
            self.assertIn(f"@import url('../vendor/{nombre}') layer(vendor);", texto)

    def test_cada_plantilla_carga_capas_antes_que_nada(self):
        for ruta in CON_CAPAS:
            with self.subTest(plantilla=ruta):
                hojas = HOJA.findall((PLANTILLAS / ruta).read_text('utf-8'))
                self.assertEqual(hojas[0], 'css/capas.css')

    def test_ninguna_plantilla_carga_lo_de_terceros_por_fuera(self):
        for ruta in CON_CAPAS:
            with self.subTest(plantilla=ruta):
                hojas = HOJA.findall((PLANTILLAS / ruta).read_text('utf-8'))
                for hoja in DE_TERCEROS:
                    self.assertNotIn(hoja, hojas)
