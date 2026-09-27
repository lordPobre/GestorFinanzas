import json
import os
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from finanzas import chat_ayuda, correo, legal


class LandingTests(TestCase):
    def test_sin_sesion_se_ve_la_landing(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'finanzas/landing.html')
        self.assertContains(respuesta, reverse('registro'))
        self.assertContains(respuesta, reverse('login'))

    def test_con_sesion_se_ve_el_inicio(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'finanzas/dashboard.html')

    def test_la_app_instalada_sin_sesion_va_al_acceso(self):
        respuesta = self.client.get(reverse('dashboard') + '?fuente=pwa')
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)

    def test_la_landing_no_trae_scripts_sin_nonce(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        for trozo in cuerpo.split('<script')[1:]:
            self.assertIn('nonce=', trozo.split('>')[0])


class AyudaTests(TestCase):
    def setUp(self):
        cache.clear()

    def _chat(self, mensajes):
        return self.client.post(reverse('ayuda_chat'), data=json.dumps({'mensajes': mensajes}),
                                content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def _contacto(self, **datos):
        return self.client.post(reverse('ayuda_contacto'), datos, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_la_landing_trae_preguntas_ayuda_y_chat(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertContains(respuesta, 'id="preguntas"')
        self.assertContains(respuesta, 'id="ayuda"')
        self.assertContains(respuesta, legal.CORREO_CONTACTO)
        self.assertContains(respuesta, reverse('ayuda_chat'))
        self.assertContains(respuesta, reverse('ayuda_contacto'))

    def test_el_chat_responde(self):
        with mock.patch.object(chat_ayuda, 'responder', return_value='Es gratis.'):
            datos = self._chat([{'rol': 'user', 'texto': '¿Es gratis?'}]).json()
        self.assertEqual(datos, {'ok': True, 'texto': 'Es gratis.'})

    def test_el_chat_avisa_cuando_no_sabe(self):
        with mock.patch.object(chat_ayuda, 'responder', return_value=None):
            datos = self._chat([{'rol': 'user', 'texto': '¿Qué hora es?'}]).json()
        self.assertTrue(datos['sin_respuesta'])

    def test_el_chat_rechaza_mensajes_vacios(self):
        self.assertEqual(self._chat([]).status_code, 400)
        self.assertEqual(self._chat([{'rol': 'assistant', 'texto': 'hola'}]).status_code, 400)

    def test_el_chat_solo_acepta_post(self):
        self.assertEqual(self.client.get(reverse('ayuda_chat')).status_code, 405)

    def test_el_chat_tiene_tope_por_visitante(self):
        with mock.patch.object(chat_ayuda, 'responder', return_value='Sí.'):
            for _ in range(10):
                self.assertEqual(self._chat([{'rol': 'user', 'texto': 'hola'}]).status_code, 200)
            self.assertEqual(self._chat([{'rol': 'user', 'texto': 'hola'}]).status_code, 429)

    def test_limpiar_ordena_el_historial(self):
        salida = chat_ayuda.limpiar([
            {'rol': 'assistant', 'texto': 'hola'},
            {'rol': 'user', 'texto': 'a'},
            {'rol': 'user', 'texto': 'b'},
            {'rol': 'system', 'texto': 'x'},
            'basura',
        ])
        self.assertEqual(salida, [{'role': 'user', 'content': 'a\nb'}])

    def test_limpiar_corta_lo_largo(self):
        salida = chat_ayuda.limpiar([{'rol': 'user', 'texto': 'x' * 5000}])
        self.assertEqual(len(salida[0]['content']), chat_ayuda.MAX_LARGO)

    def test_sin_clave_no_llama(self):
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''}):
            self.assertIsNone(chat_ayuda.responder([{'role': 'user', 'content': 'hola'}]))

    def _llamar(self, texto):
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'k'}), \
                mock.patch('anthropic.Anthropic') as cliente:
            cliente.return_value.messages.create.return_value = SimpleNamespace(
                content=[SimpleNamespace(type='text', text=texto)])
            return chat_ayuda.responder([{'role': 'user', 'content': 'hola'}])

    def test_la_ia_responde(self):
        self.assertEqual(self._llamar(' Es gratis. '), 'Es gratis.')

    def test_la_ia_sin_respuesta_devuelve_none(self):
        self.assertIsNone(self._llamar('SIN_RESPUESTA'))

    def test_el_tope_diario_corta_la_ia(self):
        with mock.patch.dict(os.environ, {'CHAT_AYUDA_TOPE_DIARIO': '1'}):
            self.assertEqual(self._llamar('Sí.'), 'Sí.')
            self.assertIsNone(self._llamar('Sí.'))

    def test_el_contacto_llega_al_correo(self):
        with mock.patch.object(correo, 'enviar', return_value=True) as enviar:
            datos = self._contacto(correo='ana@ejemplo.cl', mensaje='¿Sirve con mi banco?').json()
        self.assertTrue(datos['ok'])
        destino, asunto, texto = enviar.call_args[0][:3]
        self.assertEqual(destino, legal.CORREO_CONTACTO)
        self.assertIn('ana@ejemplo.cl', texto)
        self.assertIn('¿Sirve con mi banco?', texto)

    def test_el_contacto_revisa_el_correo(self):
        with mock.patch.object(correo, 'enviar', return_value=True) as enviar:
            respuesta = self._contacto(correo='no-es-correo', mensaje='hola')
        self.assertEqual(respuesta.status_code, 400)
        enviar.assert_not_called()

    def test_el_contacto_ignora_bots(self):
        with mock.patch.object(correo, 'enviar', return_value=True) as enviar:
            datos = self._contacto(correo='ana@ejemplo.cl', mensaje='hola', sitio='http://spam').json()
        self.assertTrue(datos['ok'])
        enviar.assert_not_called()

    def test_el_contacto_avisa_si_no_sale(self):
        with mock.patch.object(correo, 'enviar', return_value=False):
            respuesta = self._contacto(correo='ana@ejemplo.cl', mensaje='hola')
        self.assertEqual(respuesta.status_code, 502)
        self.assertIn(legal.CORREO_CONTACTO, respuesta.json()['msg'])

    def test_la_politica_declara_el_chat(self):
        cuerpo = self.client.get(reverse('privacidad')).content.decode('utf-8')
        self.assertIn('El chat de ayuda', cuerpo)
        self.assertIn('lo que escribas en el chat de ayuda', cuerpo)
