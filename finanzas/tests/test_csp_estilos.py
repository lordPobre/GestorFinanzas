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
LEGALES = ('legal_base.html', 'privacidad.html', 'terminos.html', 'seguridad.html',
           'marca_icono.html', '_consentimiento.html', '_marketing_head.html')
SCRIPTS_ACCESO = ('finapp.js', 'dispositivo.js', 'passkeys.js', 'consentimiento.js',
                  'pantallas/auth-base.js', 'pantallas/auth-base-2.js', 'pantallas/auth-vitrina.js',
                  'pantallas/login.js', 'pantallas/login-2.js', 'pantallas/registro.js',
                  'pantallas/restablecer.js', 'pantallas/verificar.js', 'pantallas/legal.js')
PANTALLAS_CON_SESION = ('base.html', '_aviso_encuesta.html', '_marca.html', '_esfera.html',
                        'dashboard.html', 'perfil.html', 'form_transaccion.html',
                        'form_gasto_pendiente.html', 'deudas.html', 'form_deuda.html',
                        'prestamos.html', 'form_persona.html', 'form_prestamo.html',
                        'suscripciones.html', 'form_suscripcion.html', 'editar_suscripcion.html',
                        'metas.html', 'crear_meta.html', 'categorias.html', 'estadisticas.html',
                        'analisis.html', 'plan.html', '_plan_ia.html', '_mes_nav.html',
                        'importar_cartola.html', 'revisar_cartola.html', 'configurar_2fa.html',
                        'codigos_respaldo.html', 'passkeys.html', 'sesiones.html', 'actividad.html',
                        'eliminar_cuenta.html')
SCRIPTS_CON_SESION = ('finapp.js', 'tour.js', 'dispositivo.js', 'pantallas/base.js', 'pantallas/base-2.js',
                      'pantallas/base-3.js', 'pantallas/base-4.js', 'pantallas/base-5.js',
                      'pantallas/estilos.js', 'pantallas/anotar.js', 'pantallas/anotar-tope.js',
                      'pantallas/recordatorios.js', 'pantallas/cuenta.js', 'pantallas/secciones.js',
                      'pantallas/saludo-cielo.js', 'pantallas/dashboard.js', 'pantallas/inicio-cifra.js',
                      'pantallas/inicio-movimientos.js', 'pantallas/inicio-esfera.js',
                      'pantallas/form-transaccion.js', 'pantallas/perfil.js', 'pantallas/perfil-2.js',
                      'pantallas/deudas.js', 'pantallas/form-deuda.js', 'pantallas/prestamos.js',
                      'pantallas/form-persona.js', 'pantallas/form-prestamo.js',
                      'pantallas/suscripciones.js', 'pantallas/form-suscripcion.js',
                      'pantallas/metas.js', 'pantallas/crear-meta.js',
                      'pantallas/categorias.js', 'pantallas/categorias-2.js', 'pantallas/categorias-topes.js',
                      'pantallas/estadisticas.js', 'pantallas/estadisticas-2.js',
                      'pantallas/analisis.js', 'pantallas/analisis-2.js',
                      'pantallas/plan.js', 'pantallas/plan-proyeccion.js', 'pantallas/plan-simulador.js',
                      'pantallas/importar-cartola.js', 'pantallas/revisar-cartola.js',
                      'pantallas/configurar-2fa.js', 'pantallas/codigos-respaldo.js',
                      'pantallas/passkeys.js', 'passkeys.js')


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

    def test_la_portada_sin_sesion_sigue_aceptando_atributos_style(self):
        directivas = _directivas(self.client.get(reverse('dashboard')))
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

    def test_las_pantallas_con_sesion_ya_limpias_no_traen_atributos_style(self):
        con_style = [nombre for nombre in PANTALLAS_CON_SESION
                     if ATRIBUTO_STYLE.search((PLANTILLAS / 'finanzas' / nombre).read_text('utf-8'))]
        self.assertEqual(con_style, [])

    def test_los_scripts_de_esas_pantallas_no_escriben_atributos_style(self):
        con_style = [nombre for nombre in SCRIPTS_CON_SESION
                     if SCRIPT_CON_STYLE.search((SCRIPTS / nombre).read_text('utf-8'))]
        self.assertEqual(con_style, [])

    def test_el_logo_de_una_marca_lleva_sus_colores_en_datos(self):
        html = Template(
            "{% load marcas %}{% marca_de 'Spotify' as m %}"
            "{% include 'finanzas/_marca.html' with clase='ini-ficha' %}"
        ).render(Context({}))
        self.assertIn('data-fondo="#', html)
        self.assertIn('data-tinta="#', html)
        self.assertNotIn('style=', html)
