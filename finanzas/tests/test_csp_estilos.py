import os
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates'
SCRIPTS = Path(settings.BASE_DIR) / 'static' / 'js'
SIN_MEDICION = {clave: '' for clave in ('GA4_ID', 'META_PIXEL_ID', 'TIKTOK_PIXEL_ID', 'X_PIXEL_ID',
                                          'X_EVENTO_REGISTRO', 'PLAUSIBLE_DOMINIO', 'PLAUSIBLE_SCRIPT')}
ATRIBUTO_STYLE = re.compile(r'\sstyle\s*=')
SCRIPT_CON_STYLE = re.compile(r'''style\s*=\s*["']|setAttribute\(\s*["']style''')
LEGALES = ('legal_base.html', 'privacidad.html', 'terminos.html', 'seguridad.html',
           'marca_icono.html', '_consentimiento.html', '_marketing_head.html')
SCRIPTS_ACCESO = ('finapp.js', 'dispositivo.js', 'passkeys.js', 'consentimiento.js',
                  'pantallas/auth-base.js', 'pantallas/auth-base-2.js', 'pantallas/auth-vitrina.js',
                  'pantallas/login.js', 'pantallas/login-2.js', 'pantallas/registro.js',
                  'pantallas/restablecer.js', 'pantallas/verificar.js', 'pantallas/legal.js')


def _directivas(respuesta):
    politica = respuesta.headers['Content-Security-Policy']
    return {d.strip().split(' ')[0]: d.strip() for d in politica.split(';') if d.strip()}


def _es_correo(ruta):
    return ruta.name.startswith('correo_') and '{% extends' not in ruta.read_text('utf-8')


@mock.patch.dict(os.environ, SIN_MEDICION)
class EstilosEnLaPoliticaTests(TestCase):

    def test_las_etiquetas_style_piden_el_nonce(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        directivas = _directivas(self.client.get(reverse('dashboard')))
        self.assertIn("'nonce-", directivas['style-src-elem'])
        self.assertNotIn('unsafe-inline', directivas['style-src-elem'])
        self.assertEqual(directivas['style-src-attr'], "style-src-attr 'unsafe-inline'")

    def test_el_acceso_y_las_legales_no_aplican_atributos_style(self):
        for nombre in ('login', 'registro', 'recuperar', 'privacidad', 'terminos', 'seguridad'):
            with self.subTest(pagina=nombre):
                directivas = _directivas(self.client.get(reverse(nombre)))
                self.assertIn("'nonce-", directivas['style-src-elem'])
                self.assertEqual(directivas['style-src-attr'], "style-src-attr 'none'")

    def test_con_pixeles_activos_la_portada_no_se_endurece(self):
        with mock.patch.dict(os.environ, {'META_PIXEL_ID': '1234567890'}):
            directivas = _directivas(self.client.get(reverse('dashboard')))
        self.assertNotIn('style-src-elem', directivas)

    def test_plausible_solo_no_quita_el_nonce(self):
        with mock.patch.dict(os.environ, {'PLAUSIBLE_DOMINIO': 'fintora.cl'}):
            directivas = _directivas(self.client.get(reverse('privacidad')))
        self.assertIn('style-src-elem', directivas)
        self.assertEqual(directivas['style-src-attr'], "style-src-attr 'none'")

    def test_las_paginas_de_error_traen_su_hoja(self):
        respuesta = self.client.get('/esta-pagina-no-existe/')
        self.assertEqual(respuesta.status_code, 404)
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('css/errores.css', cuerpo)
        self.assertNotIn('<style', cuerpo)


class PlantillasSinEstiloEnLineaTests(SimpleTestCase):

    def test_ninguna_pantalla_trae_un_bloque_style(self):
        con_style = [str(p.relative_to(PLANTILLAS)) for p in PLANTILLAS.rglob('*.html')
                     if not p.name.startswith('correo_') and '<style' in p.read_text('utf-8')]
        self.assertEqual(con_style, [])

    def test_el_acceso_y_las_legales_no_traen_atributos_style(self):
        archivos = [p for p in (PLANTILLAS / 'registration').glob('*.html') if not _es_correo(p)]
        archivos += [PLANTILLAS / 'finanzas' / nombre for nombre in LEGALES]
        con_style = [str(p.relative_to(PLANTILLAS)) for p in archivos
                     if ATRIBUTO_STYLE.search(p.read_text('utf-8'))]
        self.assertEqual(con_style, [])

    def test_los_scripts_del_acceso_no_escriben_atributos_style(self):
        con_style = [nombre for nombre in SCRIPTS_ACCESO
                     if SCRIPT_CON_STYLE.search((SCRIPTS / nombre).read_text('utf-8'))]
        self.assertEqual(con_style, [])
