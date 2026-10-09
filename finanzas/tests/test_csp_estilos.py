import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas.models import Transaccion
from finanzas.tests.test_vistas import BaseDosUsuarios

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates'
SCRIPTS = Path(settings.BASE_DIR) / 'static' / 'js'
SIN_MEDICION = {clave: '' for clave in ('GA4_ID', 'META_PIXEL_ID', 'TIKTOK_PIXEL_ID', 'X_PIXEL_ID',
                                          'X_EVENTO_REGISTRO', 'PLAUSIBLE_DOMINIO', 'PLAUSIBLE_SCRIPT')}
ATRIBUTO_STYLE = re.compile(r'\sstyle\s*=')
SCRIPT_CON_STYLE = re.compile(r'''style\s*=\s*["']|setAttribute\(\s*["']style''')
SCRIPTS_FUERA_DE_LA_PAGINA = ('sw.js',)

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
        directivas = _directivas(self.client.get(reverse('categorias')))
        self.assertIn("'nonce-", directivas['style-src-elem'])
        self.assertNotIn('unsafe-inline', directivas['style-src-elem'])
        self.assertEqual(directivas['style-src-attr'], "style-src-attr 'none'")

    def test_inicio_perfil_y_movimientos_no_aplican_atributos_style(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        gasto = Transaccion.objects.create(usuario=ana, tipo='EGRESO', monto=Decimal('1000'),
                                           categoria='Comida', fecha=date.today())
        self.client.force_login(ana)
        rutas = [reverse('dashboard'), reverse('perfil'), reverse('registrar_transaccion'),
                 reverse('crear_gasto_pendiente'), reverse('editar_transaccion', args=[gasto.pk])]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                directivas = _directivas(respuesta)
                self.assertIn("'nonce-", directivas['style-src-elem'])
                self.assertEqual(directivas['style-src-attr'], "style-src-attr 'none'")

    def test_la_portada_sin_sesion_tampoco_aplica_atributos_style(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(_directivas(respuesta)['style-src-attr'], "style-src-attr 'none'")
        self.assertContains(respuesta, 'css/portada.css')
        self.assertIsNone(ATRIBUTO_STYLE.search(respuesta.content.decode('utf-8')))

    def test_la_bienvenida_y_la_encuesta_no_aplican_atributos_style(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1', is_staff=True)
        self.client.force_login(ana)
        for nombre in ('onboarding', 'encuesta', 'encuesta_resultados'):
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(_directivas(respuesta)['style-src-attr'], "style-src-attr 'none'")
                self.assertIsNone(ATRIBUTO_STYLE.search(respuesta.content.decode('utf-8')))

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


@mock.patch.dict(os.environ, SIN_MEDICION)
class CuotasPrestamosSuscripcionesYMetasTests(BaseDosUsuarios):

    def _rutas(self):
        d = self.de_ana
        return [
            reverse('deudas'), reverse('crear_deuda'), reverse('editar_deuda', args=[d['deuda'].pk]),
            reverse('prestamos'), reverse('prestamos') + '?lado=debo',
            reverse('detalle_persona', args=[d['persona'].pk]), reverse('crear_persona'),
            reverse('crear_prestamo', args=[d['persona'].pk]),
            reverse('suscripciones'), reverse('crear_suscripcion'),
            reverse('editar_suscripcion', args=[d['sub'].pk]),
            reverse('metas'), reverse('crear_meta'), reverse('editar_meta', args=[d['meta'].pk]),
        ]

    def test_no_aplican_ni_traen_atributos_style(self):
        self.client.force_login(self.ana)
        for ruta in self._rutas():
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(_directivas(respuesta)['style-src-attr'], "style-src-attr 'none'")
                self.assertIsNone(ATRIBUTO_STYLE.search(respuesta.content.decode('utf-8')))

    def test_lo_que_depende_de_los_datos_va_en_atributos_data(self):
        self.client.force_login(self.ana)
        self.assertContains(self.client.get(reverse('deudas')), 'data-columnas="6"')
        persona = self.client.get(reverse('detalle_persona', args=[self.de_ana['persona'].pk]))
        self.assertContains(persona, 'data-ancho-pct="')
        metas = self.client.get(reverse('metas'))
        self.assertContains(metas, 'data-pct-var="0"')
        self.assertContains(metas, 'data-color-var="#')


@mock.patch.dict(os.environ, SIN_MEDICION)
class AnalisisCartolaYSeguridadTests(BaseDosUsuarios):

    RUTAS = ('categorias', 'estadisticas', 'analisis_predictivo', 'plan_plata', 'importar_cartola',
             'configurar_2fa', 'passkeys', 'sesiones_activas', 'actividad_cuenta', 'eliminar_cuenta')

    def test_no_aplican_ni_traen_atributos_style(self):
        self.client.force_login(self.ana)
        for nombre in self.RUTAS:
            with self.subTest(ruta=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(_directivas(respuesta)['style-src-attr'], "style-src-attr 'none'")
                self.assertIsNone(ATRIBUTO_STYLE.search(respuesta.content.decode('utf-8')))


class PlantillasSinEstiloEnLineaTests(SimpleTestCase):

    def test_ninguna_pantalla_trae_un_bloque_style(self):
        con_style = [str(p.relative_to(PLANTILLAS)) for p in PLANTILLAS.rglob('*.html')
                     if not p.name.startswith('correo_') and '<style' in p.read_text('utf-8')]
        self.assertEqual(con_style, [])

    def test_ninguna_plantilla_de_pantalla_trae_atributos_style(self):
        con_style = [str(p.relative_to(PLANTILLAS)) for p in PLANTILLAS.rglob('*.html')
                     if not _es_correo(p) and ATRIBUTO_STYLE.search(p.read_text('utf-8'))]
        self.assertEqual(con_style, [])

    def test_ningun_script_de_la_pagina_escribe_atributos_style(self):
        con_style = [str(p.relative_to(SCRIPTS)) for p in SCRIPTS.rglob('*.js')
                     if str(p.relative_to(SCRIPTS)) not in SCRIPTS_FUERA_DE_LA_PAGINA
                     and SCRIPT_CON_STYLE.search(p.read_text('utf-8'))]
        self.assertEqual(con_style, [])

    def test_el_logo_de_una_marca_lleva_sus_colores_en_datos(self):
        html = Template(
            "{% load marcas %}{% marca_de 'Spotify' as m %}"
            "{% include 'finanzas/_marca.html' with clase='ini-ficha' %}"
        ).render(Context({}))
        self.assertIn('data-fondo="#', html)
        self.assertIn('data-tinta="#', html)
        self.assertNotIn('style=', html)
