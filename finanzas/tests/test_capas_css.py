import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates'
HOJAS = Path(settings.BASE_DIR) / 'static' / 'css'
CAPAS = HOJAS / 'capas.css'
ORDEN = '@layer vendor, app, ajustes;'
FUERA_DE_APP = ('capas.css', 'errores.css')
ANTES_QUE_CAPAS = ('consentimiento.css',)
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
        self.assertEqual(primera, ORDEN)

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

    def test_cada_hoja_propia_va_entera_en_la_capa_app(self):
        for hoja in sorted(HOJAS.glob('*.css')):
            if hoja.name in FUERA_DE_APP:
                continue
            with self.subTest(hoja=hoja.name):
                lineas = hoja.read_text('utf-8').strip().splitlines()
                if hoja.name in ANTES_QUE_CAPAS:
                    self.assertEqual(lineas.pop(0), ORDEN)
                self.assertEqual(lineas[0], '@layer app {')
                self.assertEqual(lineas[-1], '}')
                self.assertNotIn('@layer app {', '\n'.join(lineas[1:]))
