import hmac
import json
import logging
import os
import secrets
import urllib.error
import urllib.request

from django.core.cache import cache

log = logging.getLogger('finanzas')

API = 'https://api.telegram.org/bot{token}/{metodo}'
ARCHIVO = 'https://api.telegram.org/file/bot{token}/{ruta}'
MINUTOS_CODIGO = 10
TIEMPO_ESPERA = 15


def _token():
    return os.environ.get('TELEGRAM_TOKEN', '').strip()


def bot():
    return os.environ.get('TELEGRAM_BOT', '').strip().lstrip('@')


def secreto():
    return os.environ.get('TELEGRAM_SECRETO', '').strip()


def configurado():
    return bool(_token() and bot() and secreto())


def secreto_valido(valor):
    esperado = secreto()
    return bool(esperado) and hmac.compare_digest(esperado.encode(), (valor or '').encode())


def llamar(metodo, **datos):
    if not _token():
        return None
    pedido = urllib.request.Request(API.format(token=_token(), metodo=metodo),
                                    data=json.dumps(datos).encode(), method='POST')
    pedido.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(pedido, timeout=TIEMPO_ESPERA) as respuesta:
            cuerpo = json.loads(respuesta.read())
    except urllib.error.HTTPError as e:
        log.error('Telegram rechazó %s (%s): %s', metodo, e.code, e.read().decode(errors='replace')[:200])
        return None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.error('No se pudo hablar con Telegram (%s): %s', metodo, type(e).__name__)
        return None
    return cuerpo.get('result') if cuerpo.get('ok') else None


def descargar(file_id, maximo):
    archivo = llamar('getFile', file_id=file_id) if file_id else None
    ruta = (archivo or {}).get('file_path')
    if not ruta or (archivo.get('file_size') or 0) > maximo:
        return None
    try:
        with urllib.request.urlopen(ARCHIVO.format(token=_token(), ruta=ruta), timeout=TIEMPO_ESPERA) as respuesta:
            datos = respuesta.read(maximo + 1)
    except (urllib.error.URLError, TimeoutError) as e:
        log.error('No se pudo bajar el audio de Telegram: %s', type(e).__name__)
        return None
    return datos if len(datos) <= maximo else None


def nuevo_codigo(usuario):
    codigo = secrets.token_urlsafe(18)
    cache.set(f'telegram:codigo:{codigo}', usuario.pk, MINUTOS_CODIGO * 60)
    return codigo


def usar_codigo(codigo):
    if not codigo or len(codigo) > 64:
        return None
    clave = f'telegram:codigo:{codigo}'
    pk = cache.get(clave)
    cache.delete(clave)
    return pk


def enlace(codigo):
    return f'https://t.me/{bot()}?start={codigo}'
