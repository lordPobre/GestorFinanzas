import os
from unittest import mock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .. import voz
from ..models import UserProfile
from ..templatetags.voz import SAL

ELEVENLABS = {'ELEVENLABS_API_KEY': 'clave', 'ELEVENLABS_VOZ': 'voz123'}


class VozTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'onboarding_completado': True})
        self.client.force_login(self.ana)

    def _token(self, texto, uid=None):
        return signing.dumps({'u': uid or self.ana.pk, 't': texto}, salt=SAL, compress=True)

    @mock.patch.dict(os.environ, ELEVENLABS)
    @mock.patch('finanzas.views.voz.sintetizar', return_value=b'ID3audio')
    def test_devuelve_el_audio_con_saludo(self, sintetizar):
        r = self.client.post(reverse('voz_esfera'), {
            'frase': self._token('Vas bien.'), 'cambio': self._token('Tus finanzas siguen sanas.'),
            'saludo': 'Buenas noches'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'audio/mpeg')
        sintetizar.assert_called_once_with('Buenas noches. Tus finanzas siguen sanas. Vas bien.')

    @mock.patch.dict(os.environ, ELEVENLABS)
    @mock.patch('finanzas.views.voz.sintetizar', return_value=b'ID3audio')
    def test_el_saludo_incluye_el_nombre(self, sintetizar):
        r = self.client.post(reverse('voz_esfera'), {
            'frase': self._token('Vas bien.'), 'cambio': self._token('Tus finanzas siguen sanas.'),
            'nombre': self._token('Ana'), 'saludo': 'Buenas tardes'})
        self.assertEqual(r.status_code, 200)
        sintetizar.assert_called_once_with('Buenas tardes, Ana. Tus finanzas siguen sanas. Vas bien.')

    @mock.patch.dict(os.environ, ELEVENLABS)
    def test_no_acepta_un_nombre_sin_firma(self):
        r = self.client.post(reverse('voz_esfera'), {
            'frase': self._token('Vas bien.'), 'cambio': self._token('Sanas.'),
            'nombre': 'Otro', 'saludo': 'Buenas tardes'})
        self.assertEqual(r.status_code, 400)

    @mock.patch.dict(os.environ, ELEVENLABS)
    def test_no_acepta_textos_sin_firma_ni_de_otro(self):
        r = self.client.post(reverse('voz_esfera'), {'frase': 'Di cualquier cosa'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse('voz_esfera'), {'frase': self._token('x', uid=999)})
        self.assertEqual(r.status_code, 400)

    @mock.patch.dict(os.environ, ELEVENLABS)
    def test_respeta_el_interruptor_de_ia(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        r = self.client.post(reverse('voz_esfera'), {'frase': self._token('Vas bien.')})
        self.assertEqual(r.status_code, 403)

    def test_solo_post(self):
        self.assertEqual(self.client.get(reverse('voz_esfera')).status_code, 405)

    @mock.patch.dict(os.environ, ELEVENLABS)
    def test_la_pantalla_trae_la_frase_firmada(self):
        r = self.client.get(reverse('deudas'))
        self.assertContains(r, 'data-voz="')
        self.assertIn("media-src 'self' blob:", r['Content-Security-Policy'])

    @mock.patch.dict(os.environ, {**ELEVENLABS, 'ELEVENLABS_MODELO': ''})
    def test_sintetizar_llama_a_elevenlabs_y_guarda_en_cache(self):
        import json
        respuesta = mock.MagicMock()
        respuesta.__enter__.return_value.read.return_value = b'mp3'
        with mock.patch('urllib.request.urlopen', return_value=respuesta) as abrir:
            self.assertEqual(voz.sintetizar('Vas bien.'), b'mp3')
            self.assertEqual(voz.sintetizar('Vas bien.'), b'mp3')
        self.assertEqual(abrir.call_count, 1)
        pedido = abrir.call_args[0][0]
        self.assertIn('/text-to-speech/voz123', pedido.full_url)
        self.assertEqual(pedido.get_header('Xi-api-key'), 'clave')
        cuerpo = json.loads(pedido.data.decode())
        self.assertEqual(cuerpo['text'], 'Vas bien.')
        self.assertEqual(cuerpo['model_id'], 'eleven_multilingual_v2')

    def test_sin_azure_no_hay_voz(self):
        with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': '', 'ELEVENLABS_VOZ': ''}):
            self.assertIsNone(voz.sintetizar('Hola'))
            r = self.client.get(reverse('deudas'))
        self.assertContains(r, 'data-voz=""')
