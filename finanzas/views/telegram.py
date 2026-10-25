import json
import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .. import fechas, telegram
from ..models import ChatTelegram, Transaccion
from ..seguridad import sumar
from .api import TOPE_HORA, _con_ia, _crear

log = logging.getLogger('finanzas')

AYUDA = ('Escríbeme lo que gastaste, como «5 lucas en café» o «ayer 12.990 supermercado», y lo anoto. '
         'Si tienes el análisis con IA activado, también puedes mandarme un audio.')
SIN_CUENTA = 'Para empezar, conecta tu cuenta desde Fintora: Perfil → Anotar desde afuera → Conectar Telegram.'


def _decir(chat_id, texto, botones=None):
    datos = {'chat_id': chat_id, 'text': texto}
    if botones:
        datos['reply_markup'] = {'inline_keyboard': botones}
    telegram.llamar('sendMessage', **datos)


def _conectar(chat_id, codigo, de):
    pk = telegram.usar_codigo(codigo)
    usuario = User.objects.filter(pk=pk, is_active=True).first() if pk else None
    if usuario is None:
        if ChatTelegram.objects.filter(chat_id=chat_id).exists():
            return _decir(chat_id, AYUDA)
        return _decir(chat_id, ('Ese enlace ya no sirve. ' if codigo else '') + SIN_CUENTA)
    nombre = str(de.get('username') or de.get('first_name') or '')[:80]
    with transaction.atomic():
        ChatTelegram.objects.filter(Q(usuario=usuario) | Q(chat_id=chat_id)).delete()
        ChatTelegram.objects.create(usuario=usuario, chat_id=chat_id, nombre=nombre)
    _decir(chat_id, 'Listo, este chat quedó conectado con tu cuenta de Fintora. ' + AYUDA)


def _oir(usuario, audio):
    from ..oido import MAX_BYTES, transcribir
    from ..voz import configurada

    if not (_con_ia(usuario) and configurada()):
        return None, 'Los audios se leen con IA. Actívala en Perfil o escríbeme el gasto.'
    if (audio.get('file_size') or 0) > MAX_BYTES:
        return None, 'El audio es muy largo. Prueba con uno más corto.'
    datos = telegram.descargar(str(audio.get('file_id') or ''), MAX_BYTES)
    texto = transcribir(datos, str(audio.get('mime_type') or 'audio/ogg')) if datos else None
    if not texto:
        return None, 'No entendí el audio. Prueba otra vez o escríbelo.'
    return texto, ''


def _mensaje(mensaje):
    chat = mensaje.get('chat') or {}
    chat_id = chat.get('id')
    if chat.get('type') != 'private' or not isinstance(chat_id, int):
        return
    texto = ' '.join(str(mensaje.get('text') or '').split())
    if texto.startswith('/start'):
        return _conectar(chat_id, texto[6:].strip(), mensaje.get('from') or {})

    vinculo = ChatTelegram.objects.select_related('usuario').filter(chat_id=chat_id, usuario__is_active=True).first()
    if vinculo is None:
        return _decir(chat_id, SIN_CUENTA)
    usuario = vinculo.usuario
    if texto == '/desconectar':
        vinculo.delete()
        return _decir(chat_id, 'Desconecté este chat de tu cuenta. Para volver, usa Conectar Telegram en Perfil.')

    usados, _ = sumar(f'api:{usuario.pk}', 3600)
    if usados > TOPE_HORA:
        return _decir(chat_id, 'Anotaste muchas cosas seguidas. Espera un rato.')

    oido = ''
    audio = mensaje.get('voice') or mensaje.get('audio')
    if audio:
        oido, problema = _oir(usuario, audio)
        if oido is None:
            return _decir(chat_id, problema)
        texto = oido
    if not texto or texto.startswith('/'):
        return _decir(chat_id, AYUDA)

    resultado = json.loads(_crear({'texto': texto[:300]}, usuario).content or b'{}')
    ChatTelegram.objects.filter(pk=vinculo.pk).update(usado=timezone.now())
    if not resultado.get('ok'):
        return _decir(chat_id, resultado.get('msg') or 'No pude anotarlo.')
    cuerpo = f'«{oido}»\n{resultado["texto"]}' if oido else resultado['texto']
    _decir(chat_id, cuerpo, [[{'text': 'Deshacer', 'callback_data': f'deshacer:{resultado["id"]}'}]])


def _boton(consulta):
    mensaje = consulta.get('message') or {}
    chat_id = (mensaje.get('chat') or {}).get('id')
    datos = str(consulta.get('data') or '')
    aviso = ''
    vinculo = (ChatTelegram.objects.filter(chat_id=chat_id, usuario__is_active=True).first()
               if isinstance(chat_id, int) else None)
    if vinculo and datos.startswith('deshacer:') and datos[9:].isdigit():
        tx = Transaccion.objects.filter(pk=int(datos[9:]), usuario_id=vinculo.usuario_id, origen=Transaccion.API,
                                        fecha__gte=fechas.hoy() - timedelta(days=1)).first()
        if tx is None:
            aviso = 'Ese ya no se puede deshacer desde aquí.'
        else:
            tx.delete()
            aviso = 'Lo borré.'
            telegram.llamar('editMessageText', chat_id=chat_id, message_id=mensaje.get('message_id'),
                            text=f'{mensaje.get("text") or ""}\n\nLo borré.')
    telegram.llamar('answerCallbackQuery', callback_query_id=str(consulta.get('id') or ''), text=aviso)


@csrf_exempt
@require_POST
def webhook(request):
    if not telegram.secreto_valido(request.headers.get('X-Telegram-Bot-Api-Secret-Token')):
        return JsonResponse({'ok': False}, status=403)
    try:
        update = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'ok': True})
    if not isinstance(update, dict) or not cache.add(f'telegram:update:{update.get("update_id")}', 1, 86400):
        return JsonResponse({'ok': True})
    try:
        if isinstance(update.get('callback_query'), dict):
            _boton(update['callback_query'])
        elif isinstance(update.get('message'), dict):
            _mensaje(update['message'])
    except Exception:
        log.exception('El bot de Telegram no pudo responder')
    return JsonResponse({'ok': True})
