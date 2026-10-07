import os
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates'
SIN_MEDICION = {clave: '' for clave in ('GA4_ID', 'META_PIXEL_ID', 'TIKTOK_PIXEL_ID', 'X_PIXEL_ID',
                                          'X_EVENTO_REGISTRO', 'PLAUSIBLE_DOMINIO', 'PLAUSIBLE_SCRIPT')}


def _directivas(respuesta):
    politica = respuesta.headers['Content-Security-Policy']
    return {d.strip().split(' ')[0]: d.strip() for d in politica.split(';') if d.strip()}


@mock.patch.dict(os.environ, SIN_MEDICION)
class EstilosEnLaPoliticaTests(TestCase):

    def test_las_etiquetas_style_piden_el_nonce(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        directivas = _directivas(self.client.get(reverse('dashboard')))
        self.assertIn("'nonce-", directivas['style-src-elem'])
        self.assertNotIn('unsafe-inline', directivas['style-src-elem'])
        self.assertEqual(directivas['style-src-attr'], "style-src-attr 'unsafe-inline'")

    def test_el_acceso_y_las_legales_tambien(self):
        for nombre in ('login', 'registro', 'privacidad'):
            with self.subTest(pagina=nombre):
                self.assertIn('style-src-elem', _directivas(self.client.get(reverse(nombre))))

    def test_con_pixeles_activos_la_portada_no_se_endurece(self):
        with mock.patch.dict(os.environ, {'META_PIXEL_ID': '1234567890'}):
            directivas = _directivas(self.client.get(reverse('dashboard')))
        self.assertNotIn('style-src-elem', directivas)

    def test_plausible_solo_no_quita_el_nonce(self):
        with mock.patch.dict(os.environ, {'PLAUSIBLE_DOMINIO': 'fintora.cl'}):
            directivas = _directivas(self.client.get(reverse('privacidad')))
        self.assertIn('style-src-elem', directivas)

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
