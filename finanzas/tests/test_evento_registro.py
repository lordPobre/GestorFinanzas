import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import marketing

PIXELES = {
    'GA4_ID': 'G-PRUEBA1',
    'META_PIXEL_ID': '1234567890',
    'TIKTOK_PIXEL_ID': 'CPRUEBA',
    'X_PIXEL_ID': 'oprueba',
    'X_EVENTO_REGISTRO': 'tw-oprueba-abc12',
}
VACIO = {k: '' for k in PIXELES}


class EventoRegistroTests(TestCase):
    def _con_evento(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'Clave-segura-2026')
        self.client.force_login(ana)
        sesion = self.client.session
        sesion[marketing.CLAVE_EVENTO] = True
        sesion.save()

    def test_el_registro_deja_marcado_el_evento(self):
        self.client.post(reverse('registro'), {
            'username': 'beto',
            'password1': 'Clave-segura-2026',
            'password2': 'Clave-segura-2026',
            'email_perfil': 'beto@ejemplo.cl',
            'nombre_completo': 'Beto',
            'acepta_politica': '1',
        })
        self.assertTrue(self.client.session.get(marketing.CLAVE_EVENTO))

    def test_la_pantalla_siguiente_manda_el_evento(self):
        self._con_evento()
        with mock.patch.dict(os.environ, PIXELES):
            respuesta = self.client.get(reverse('onboarding'))
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('data-evento="registro"', cuerpo)
        self.assertIn('data-x-registro="tw-oprueba-abc12"', cuerpo)
        self.assertNotIn('data-cookies-aceptar', cuerpo)
        self.assertIn('connect.facebook.net', respuesta.headers['Content-Security-Policy'])

    def test_el_evento_sale_una_sola_vez(self):
        self._con_evento()
        with mock.patch.dict(os.environ, PIXELES):
            self.client.get(reverse('onboarding'))
            respuesta = self.client.get(reverse('dashboard'))
        self.assertNotIn('data-evento', respuesta.content.decode('utf-8'))
        self.assertNotIn('facebook', respuesta.headers['Content-Security-Policy'])

    def test_sin_pixeles_no_hay_evento(self):
        self._con_evento()
        with mock.patch.dict(os.environ, VACIO):
            respuesta = self.client.get(reverse('onboarding'))
        self.assertNotIn('data-evento', respuesta.content.decode('utf-8'))
        self.assertNotIn('facebook', respuesta.headers['Content-Security-Policy'])
