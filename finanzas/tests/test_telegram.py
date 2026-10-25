import json
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .. import telegram
from ..models import ChatTelegram, Transaccion, UserProfile

ENTORNO = {'TELEGRAM_TOKEN': 't', 'TELEGRAM_BOT': 'FintoraBot', 'TELEGRAM_SECRETO': 's3creto'}


@mock.patch.dict('os.environ', ENTORNO)
@mock.patch('finanzas.telegram.llamar')
class TelegramTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(usuario=self.ana,
                                                              defaults={'onboarding_completado': True})
        self.numero = 1

    def _enviar(self, update, secreto='s3creto', numero=None):
        if numero is None:
            numero = self.numero
            self.numero += 1
        return self.client.post(reverse('telegram_webhook'), json.dumps({'update_id': numero, **update}),
                                content_type='application/json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secreto)

    def _mensaje(self, chat=55, **campos):
        return {'message': {'message_id': 1, 'chat': {'id': chat, 'type': 'private'},
                            'from': {'id': chat, 'first_name': 'Ana'}, **campos}}

    def _texto(self, texto, chat=55, **otros):
        return self._enviar(self._mensaje(chat, text=texto), **otros)

    def _conectar(self, chat=55):
        self._texto(f'/start {telegram.nuevo_codigo(self.ana)}', chat)

    def _dicho(self, llamar):
        return llamar.call_args_list[-1].kwargs

    def test_sin_secreto_se_rechaza(self, llamar):
        r = self._texto(f'/start {telegram.nuevo_codigo(self.ana)}', secreto='otro')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(ChatTelegram.objects.exists())

    def test_el_codigo_sirve_una_vez(self, llamar):
        codigo = telegram.nuevo_codigo(self.ana)
        self._texto(f'/start {codigo}', 55)
        self._texto(f'/start {codigo}', 66)
        self.assertEqual(list(ChatTelegram.objects.values_list('chat_id', flat=True)), [55])

    def test_anota_y_deshace(self, llamar):
        self._conectar()
        self._texto('5 lucas café')
        tx = Transaccion.objects.get(usuario=self.ana)
        self.assertEqual(int(tx.monto), 5000)
        dicho = self._dicho(llamar)
        self.assertIn('Anotado', dicho['text'])
        self.assertEqual(dicho['reply_markup']['inline_keyboard'][0][0]['callback_data'], f'deshacer:{tx.pk}')
        self._enviar({'callback_query': {'id': 'c1', 'data': f'deshacer:{tx.pk}',
                                         'message': {'message_id': 9, 'chat': {'id': 55, 'type': 'private'},
                                                     'text': dicho['text']}}})
        self.assertFalse(Transaccion.objects.filter(pk=tx.pk).exists())

    def test_otro_chat_no_deshace(self, llamar):
        self._conectar()
        self._texto('5 lucas café')
        tx = Transaccion.objects.get(usuario=self.ana)
        self._enviar({'callback_query': {'id': 'c1', 'data': f'deshacer:{tx.pk}',
                                         'message': {'message_id': 9, 'chat': {'id': 66, 'type': 'private'}}}})
        self.assertTrue(Transaccion.objects.filter(pk=tx.pk).exists())

    def test_chat_sin_cuenta_no_anota(self, llamar):
        self._texto('5 lucas café', 99)
        self.assertFalse(Transaccion.objects.exists())
        self.assertIn('conecta tu cuenta', self._dicho(llamar)['text'])

    def test_grupo_se_ignora(self, llamar):
        self._conectar()
        self._enviar({'message': {'message_id': 1, 'chat': {'id': 55, 'type': 'group'}, 'text': '5 lucas café'}})
        self.assertFalse(Transaccion.objects.exists())

    def test_update_repetido_se_ignora(self, llamar):
        self._conectar()
        self._texto('5 lucas café', numero=500)
        self._texto('5 lucas café', numero=500)
        self.assertEqual(Transaccion.objects.count(), 1)

    def test_desconectar(self, llamar):
        self._conectar()
        self._texto('/desconectar')
        self.assertFalse(ChatTelegram.objects.exists())

    @mock.patch('finanzas.telegram.descargar')
    def test_audio_sin_ia_no_se_baja(self, descargar, llamar):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        self._conectar()
        self._enviar(self._mensaje(voice={'file_id': 'a1', 'file_size': 4000, 'mime_type': 'audio/ogg'}))
        descargar.assert_not_called()
        self.assertIn('IA', self._dicho(llamar)['text'])

    @mock.patch('finanzas.voz.configurada', return_value=True)
    @mock.patch('finanzas.oido.transcribir', return_value='5 lucas café')
    @mock.patch('finanzas.telegram.descargar', return_value=b'x' * 4000)
    def test_audio_con_ia(self, descargar, transcribir, configurada, llamar):
        self.perfil.analisis_ia = True
        self.perfil.save(update_fields=['analisis_ia'])
        self._conectar()
        self._enviar(self._mensaje(voice={'file_id': 'a1', 'file_size': 4000, 'mime_type': 'audio/ogg'}))
        self.assertEqual(int(Transaccion.objects.get().monto), 5000)
        self.assertTrue(self._dicho(llamar)['text'].startswith('«5 lucas café»'))

    def test_perfil_muestra_el_enlace(self, llamar):
        self.client.force_login(self.ana)
        self.assertContains(self.client.get(reverse('clave_api')), 'https://t.me/FintoraBot?start=')
        self._conectar()
        r = self.client.get(reverse('clave_api'))
        self.assertContains(r, 'Telegram conectado')
        self.client.post(reverse('clave_api'), {'accion': 'telegram_quitar'})
        self.assertFalse(ChatTelegram.objects.exists())
