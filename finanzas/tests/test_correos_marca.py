import base64
import os
from unittest import mock

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from .. import correo


PLANTILLAS = [
    'registration/correo_recuperar.html',
    'registration/correo_verificar.html',
    'registration/correo_alta.html',
    'registration/correo_aparato.html',
    'registration/correo_cambio.html',
    'registration/correo_cambio_aviso.html',
    'registration/correo_registro_repetido.html',
    'finanzas/correo_inactividad.html',
    'finanzas/correo_pagos.html',
    'finanzas/correo_politica.html',
]

CONTEXTO = {
    'usuario': {'username': 'ana'}, 'enlace': 'http://127.0.0.1:8000/x', 'horas': 1,
    'dias': 30, 'meses': 12, 'nombre': 'Ana', 'mes': 'octubre', 'anio': 2026,
    'cantidad': 2, 'atrasados': 1, 'total': '$20.000',
    'grupos': [
        {'titulo': 'Cuotas de compras a plazo', 'filas': [
            {'nombre': 'notebook', 'detalle': 'Cuota 3 de 12', 'monto': '$10.000', 'atrasado': False},
        ]},
        {'titulo': 'Suscripciones', 'filas': [
            {'nombre': 'Plan celular', 'detalle': '20 de octubre', 'monto': '$10.000', 'atrasado': True},
        ]},
    ],
    'por_cobrar': [{'nombre': 'Javiera', 'detalle': 'Préstamo', 'monto': '$45.000'}],
    'username': 'ana', 'aparato': 'Chrome en macOS', 'nuevo': 'nuevo@ejemplo.cl',
    'entrar': 'http://127.0.0.1:8000/login/', 'recuperar': 'http://127.0.0.1:8000/recuperar/',
    'version': '1.10', 'vigente_desde': '1 de diciembre de 2026', 'cambios': [('Telegram', 'Pasa por sus servidores.')],
    'enlace_perfil': 'http://127.0.0.1:8000/perfil/', 'correo_contacto': 'contacto@fintora.cl',
}


class PlantillasDeCorreoTests(SimpleTestCase):

    def test_todas_usan_la_cabecera_en_linea_y_no_dicen_rekon(self):
        for nombre in PLANTILLAS:
            with self.subTest(nombre=nombre):
                html = render_to_string(nombre, CONTEXTO)
                self.assertIn('src="cid:fintora-cabecera"', html)
                self.assertNotIn('Rekon', html)
                self.assertNotIn('pythonanywhere', html)

    def test_el_pie_usa_el_mismo_sitio_que_el_enlace(self):
        for nombre in PLANTILLAS:
            with self.subTest(nombre=nombre):
                html = render_to_string(nombre, CONTEXTO)
                self.assertIn('href="http://127.0.0.1:8000' + reverse('privacidad') + '"', html)
                self.assertIn('href="http://127.0.0.1:8000' + reverse('terminos') + '"', html)

    def test_el_aviso_muestra_fichas_vencidos_y_lo_que_te_deben(self):
        html = render_to_string('finanzas/correo_pagos.html', CONTEXTO)
        self.assertIn('>N</div>', html)
        self.assertIn('1 de ellos ya venció', html)
        self.assertIn('· sin pagar', html)
        self.assertIn('Y a ti te deben', html)


class CorreosClarosTests(SimpleTestCase):

    def test_todos_van_en_papel_crema_y_con_un_boton_en_tinta(self):
        for nombre in PLANTILLAS:
            with self.subTest(nombre=nombre):
                html = render_to_string(nombre, CONTEXTO)
                self.assertIn('background-color:#F3EFE7', html)
                self.assertIn('bgcolor="#1E1A15"', html)
                self.assertNotIn('#0f0e0c', html)
                self.assertNotIn('Manrope', html)

    def test_los_que_eran_solo_texto_ya_tienen_html(self):
        for nombre in ('aparato', 'cambio', 'cambio_aviso', 'registro_repetido'):
            with self.subTest(nombre=nombre):
                html = render_to_string(f'registration/correo_{nombre}.html', CONTEXTO)
                self.assertIn('<!DOCTYPE html>', html)


class EnvioDeCorreoTests(SimpleTestCase):

    @mock.patch.dict(os.environ, {'CORREO_FROM': 'Rekon <no-responder@fintora.cl>'})
    def test_el_remitente_siempre_se_llama_fintora(self):
        cuerpo = correo.cuerpo_resend('ana@ejemplo.cl', 'Hola', 'texto')
        self.assertEqual(cuerpo['from'], 'Fintora <no-responder@fintora.cl>')

    def test_la_cabecera_viaja_como_imagen_en_linea(self):
        cuerpo = correo.cuerpo_resend('ana@ejemplo.cl', 'Hola', 'texto', '<img src="cid:fintora-cabecera">')
        adjunto = cuerpo['attachments'][0]
        self.assertEqual(adjunto['content_id'], 'fintora-cabecera')
        self.assertEqual(adjunto['filename'], 'correo-cabecera.png')
        self.assertTrue(base64.b64decode(adjunto['content']).startswith(b'\x89PNG'))

    def test_sin_imagen_no_hay_adjuntos(self):
        cuerpo = correo.cuerpo_resend('ana@ejemplo.cl', 'Hola', 'texto', '<p>hola</p>')
        self.assertNotIn('attachments', cuerpo)

    @override_settings(DEBUG=True)
    @mock.patch.dict(os.environ, {'SITE_URL': 'https://finanzas.pythonanywhere.com'})
    def test_en_local_el_enlace_usa_el_sitio_donde_estas(self):
        request = RequestFactory().get('/', HTTP_HOST='127.0.0.1:8000')
        self.assertEqual(correo.url_absoluta(request, '/recuperar/x/'), 'http://127.0.0.1:8000/recuperar/x/')

    @override_settings(DEBUG=False)
    @mock.patch.dict(os.environ, {'SITE_URL': 'https://fintora.cl'})
    def test_en_produccion_el_enlace_usa_site_url(self):
        request = RequestFactory().get('/', HTTP_HOST='interno:8000')
        self.assertEqual(correo.url_absoluta(request, '/recuperar/x/'), 'https://fintora.cl/recuperar/x/')
