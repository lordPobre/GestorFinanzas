import os
from unittest import mock

from django.test import SimpleTestCase

from core.settings import limpiar_evento_sentry, muestreo_sentry


def _contexto(ruta):
    return {'wsgi_environ': {'PATH_INFO': ruta}}


class MuestreoSentryTests(SimpleTestCase):

    def test_por_defecto_se_muestrea_el_cinco_por_ciento(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('SENTRY_TRACES', None)
            self.assertEqual(muestreo_sentry(_contexto('/cuotas/')), 0.05)

    def test_la_variable_cambia_la_tasa_y_se_acota(self):
        with mock.patch.dict(os.environ, {'SENTRY_TRACES': '0.2'}):
            self.assertEqual(muestreo_sentry(_contexto('/')), 0.2)
        with mock.patch.dict(os.environ, {'SENTRY_TRACES': '7'}):
            self.assertEqual(muestreo_sentry(_contexto('/')), 1.0)
        with mock.patch.dict(os.environ, {'SENTRY_TRACES': 'mucho'}):
            self.assertEqual(muestreo_sentry(_contexto('/')), 0.0)

    def test_la_salud_y_los_estaticos_no_se_muestrean(self):
        for ruta in ('/salud/', '/static/css/finapp.css', '/sw.js'):
            self.assertEqual(muestreo_sentry(_contexto(ruta)), 0.0, ruta)

    def test_las_trazas_tambien_se_limpian(self):
        evento = {'type': 'transaction', 'user': {'id': 1},
                  'request': {'url': 'https://fintora.cl/recuperar/abc123/', 'cookies': {'x': 'y'},
                              'headers': {'Cookie': 'x', 'User-Agent': 'z'}}}
        limpio = limpiar_evento_sentry(evento, {})
        self.assertNotIn('user', limpio)
        self.assertNotIn('cookies', limpio['request'])
        self.assertEqual(limpio['request']['headers'], {'User-Agent': 'z'})
        self.assertEqual(limpio['request']['url'], 'https://fintora.cl/recuperar/[filtrado]/')
