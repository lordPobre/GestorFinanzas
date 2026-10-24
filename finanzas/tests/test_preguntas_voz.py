import json
import os
import urllib.error
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .. import legal
from ..ia_preguntas import usadas_hoy
from ..models import UserProfile
from ..oido import MAX_BYTES

CLAVES = {'ELEVENLABS_API_KEY': 'k', 'ELEVENLABS_VOZ': 'v'}


def _respuesta(datos):
    falsa = mock.MagicMock()
    falsa.__enter__.return_value.read.return_value = json.dumps(datos).encode()
    return falsa


class PreguntarConVozTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'onboarding_completado': True, 'analisis_ia': True,
                                        'politica_version': legal.VERSION})
        self.client.force_login(self.ana)

    def _audio(self, tamano=4000, tipo='audio/webm'):
        return SimpleUploadedFile('pregunta', b'\x1a' * tamano, content_type=tipo)

    def _oir(self, respuesta=None, error=None, **audio):
        abrir = mock.Mock(side_effect=error) if error else mock.Mock(return_value=_respuesta(respuesta or {}))
        with mock.patch.dict(os.environ, CLAVES), mock.patch('urllib.request.urlopen', abrir):
            r = self.client.post(reverse('esfera_oir'), {'audio': self._audio(**audio)},
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        return r, abrir

    def test_devuelve_el_texto_sin_descontar_pregunta(self):
        r, abrir = self._oir({'text': '  ¿Cuánto me   queda este mes? '})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'ok': True, 'texto': '¿Cuánto me queda este mes?'})
        self.assertEqual(usadas_hoy(self.ana.pk), 0)
        pedido = abrir.call_args.args[0]
        self.assertIn(b'name="model_id"\r\n\r\nscribe_v2', pedido.data)
        self.assertIn(b'name="language_code"\r\n\r\nspa', pedido.data)
        self.assertIn(b'Content-Type: audio/webm', pedido.data)

    def test_sin_palabras_es_no_entendi(self):
        for texto in ('', '...', '   '):
            with self.subTest(texto=texto):
                r, _ = self._oir({'text': texto})
                self.assertEqual(r.json()['motivo'], 'no_entendi')
        self.assertEqual(usadas_hoy(self.ana.pk), 0)

    def test_si_elevenlabs_falla(self):
        r, _ = self._oir(error=urllib.error.URLError('caído'))
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.json()['motivo'], 'oido')

    def test_rechaza_lo_que_no_es_audio(self):
        r, abrir = self._oir({'text': 'hola'}, tipo='video/mp4')
        self.assertEqual(r.status_code, 400)
        abrir.assert_not_called()

    def test_rechaza_audios_vacios_o_grandes(self):
        for tamano in (10, MAX_BYTES + 1):
            with self.subTest(tamano=tamano):
                r, abrir = self._oir({'text': 'hola'}, tamano=tamano)
                self.assertIn(r.status_code, (400, 413))
                abrir.assert_not_called()

    def test_acepta_el_audio_de_safari(self):
        r, _ = self._oir({'text': 'hola'}, tipo='audio/mp4')
        self.assertTrue(r.json()['ok'])

    def test_con_el_tope_no_transcribe(self):
        with mock.patch('finanzas.views.preguntas.usadas_hoy', return_value=999):
            r, abrir = self._oir({'text': 'hola'})
        self.assertEqual(r.json()['motivo'], 'tope')
        abrir.assert_not_called()

    def test_sin_ia_no_transcribe(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        r, abrir = self._oir({'text': 'hola'})
        self.assertEqual(r.status_code, 403)
        abrir.assert_not_called()

    def test_sin_elevenlabs_configurado(self):
        with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': '', 'ELEVENLABS_VOZ': ''}):
            r = self.client.post(reverse('esfera_oir'), {'audio': self._audio()})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['motivo'], 'sin_oido')

    def test_el_panel_trae_el_microfono_solo_si_hay_voz(self):
        with mock.patch.dict(os.environ, CLAVES):
            r = self.client.get(reverse('dashboard'))
        self.assertContains(r, f'data-url-oir="{reverse("esfera_oir")}"')
        self.assertContains(r, 'data-charla-mic')
        with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': '', 'ELEVENLABS_VOZ': ''}):
            r = self.client.get(reverse('dashboard'))
        self.assertNotContains(r, 'data-url-oir')

    def test_el_micrófono_solo_para_la_propia_app(self):
        r = self.client.get(reverse('dashboard'))
        politica = r['Permissions-Policy']
        self.assertIn('microphone=(self)', politica)
        self.assertIn('camera=()', politica)
