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
        parche = mock.patch('finanzas.voz._almacen', return_value=None)
        parche.start()
        self.addCleanup(parche.stop)
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

    @mock.patch.dict(os.environ, {**ELEVENLABS, 'ELEVENLABS_MODELO': '', 'ELEVENLABS_VELOCIDAD': ''})
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
        self.assertEqual(cuerpo['voice_settings']['speed'], 0.9)

    @mock.patch.dict(os.environ, {**ELEVENLABS, 'ELEVENLABS_MODELO': '', 'ELEVENLABS_VELOCIDAD': ''})
    def test_los_numeros_llegan_en_palabras(self):
        import json
        respuesta = mock.MagicMock()
        respuesta.__enter__.return_value.read.return_value = b'mp3'
        with mock.patch('urllib.request.urlopen', return_value=respuesta) as abrir:
            voz.sintetizar('Llevas el 48 por ciento. Te quedan 412.300 pesos.')
        cuerpo = json.loads(abrir.call_args[0][0].data.decode())
        self.assertEqual(cuerpo['text'], 'Llevas el cuarenta y ocho por ciento. '
                                         'Te quedan cuatrocientos doce mil trescientos pesos.')

    @mock.patch.dict(os.environ, {**ELEVENLABS, 'ELEVENLABS_MODELO': ''})
    def test_la_velocidad_se_ajusta_y_tiene_limites(self):
        import json
        respuesta = mock.MagicMock()
        respuesta.__enter__.return_value.read.return_value = b'mp3'
        for valor, esperado in (('0.85', 0.85), ('3', 1.2), ('0.1', 0.7), ('rapido', 0.9)):
            with self.subTest(valor=valor), mock.patch.dict(os.environ, {'ELEVENLABS_VELOCIDAD': valor}), \
                    mock.patch('urllib.request.urlopen', return_value=respuesta) as abrir:
                cache.clear()
                voz.sintetizar('Vas bien.')
                cuerpo = json.loads(abrir.call_args[0][0].data.decode())
                self.assertEqual(cuerpo['voice_settings']['speed'], esperado)

    def test_sin_azure_no_hay_voz(self):
        with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': '', 'ELEVENLABS_VOZ': ''}):
            self.assertIsNone(voz.sintetizar('Hola'))
            r = self.client.get(reverse('deudas'))
        self.assertContains(r, 'data-voz=""')


@mock.patch.dict(os.environ, {**ELEVENLABS, 'ELEVENLABS_MODELO': '', 'ELEVENLABS_VELOCIDAD': ''})
class VozEnR2Tests(TestCase):

    def setUp(self):
        from django.core.files.storage import InMemoryStorage
        cache.clear()
        self.almacen = InMemoryStorage()
        parche = mock.patch('finanzas.voz._almacen', return_value=self.almacen)
        parche.start()
        self.addCleanup(parche.stop)
        self.respuesta = mock.MagicMock()
        self.respuesta.__enter__.return_value.read.return_value = b'mp3'

    def _mas_tarde(self, horas):
        from datetime import timedelta

        from django.utils import timezone
        reloj = mock.MagicMock()
        reloj.now.return_value = timezone.now() + timedelta(hours=horas)
        return mock.patch('finanzas.voz.timezone', reloj)

    def test_el_audio_queda_en_r2_y_no_en_la_base(self):
        with mock.patch('urllib.request.urlopen', return_value=self.respuesta) as abrir:
            self.assertEqual(voz.sintetizar('Vas bien.'), b'mp3')
            self.assertEqual(voz.sintetizar('Vas bien.'), b'mp3')
        self.assertEqual(abrir.call_count, 1)
        _, archivos = self.almacen.listdir('voz')
        self.assertEqual(len(archivos), 1)
        import hashlib
        huella = hashlib.sha256(b'voz123|eleven_multilingual_v2|0.9|Vas bien.').hexdigest()
        self.assertEqual(archivos, [f'{huella}.mp3'])
        self.assertIsNone(cache.get('voz:' + huella))

    def test_pasadas_cinco_horas_se_vuelve_a_pedir(self):
        with mock.patch('urllib.request.urlopen', return_value=self.respuesta) as abrir:
            voz.sintetizar('Vas bien.')
            with self._mas_tarde(6):
                self.assertEqual(voz.sintetizar('Vas bien.'), b'mp3')
        self.assertEqual(abrir.call_count, 2)
        _, archivos = self.almacen.listdir('voz')
        self.assertEqual(len(archivos), 1)

    def test_la_limpieza_borra_solo_lo_vencido(self):
        with mock.patch('urllib.request.urlopen', return_value=self.respuesta):
            voz.sintetizar('Vas bien.')
        with self._mas_tarde(4):
            self.assertEqual(voz.limpiar_audios(), 0)
        with self._mas_tarde(6):
            self.assertEqual(voz.limpiar_audios(), 1)
        _, archivos = self.almacen.listdir('voz')
        self.assertEqual(archivos, [])

    def test_el_comando_cuenta_lo_borrado(self):
        from io import StringIO

        from django.core.management import call_command
        salida = StringIO()
        call_command('limpiar_audios', stdout=salida)
        self.assertIn('borrados: 0', salida.getvalue())
