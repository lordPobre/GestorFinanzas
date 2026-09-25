import json
import logging
import os
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger('finanzas')

TIEMPO_ESPERA = 10
URL_RESEND = 'https://api.resend.com/emails'
AGENTE = 'Rekon/1.0 (+https://github.com/lordPobre/GestorFinanzas)'


def configurado():
    return bool(os.environ.get('RESEND_API_KEY'))


def _remitente():
    return os.environ.get('CORREO_FROM') or settings.DEFAULT_FROM_EMAIL


def _staging_sin_correo():
    return bool(getattr(settings, 'ES_STAGING', False)
                and not getattr(settings, 'CORREO_EN_STAGING', False))


def _pedir(peticion):
    peticion.add_header('User-Agent', AGENTE)
    peticion.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
            cuerpo = json.loads(respuesta.read().decode() or '{}')
            log.info('Correo aceptado: %s', cuerpo.get('id', 'sin id'))
            return True
    except urllib.error.HTTPError as e:
        log.error('Resend devolvió %s: %s', e.code, e.read().decode()[:300])
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.error('No se pudo hablar con Resend: %s', e)
    return False


def enviar(destino, asunto, texto, html=None):
    if _staging_sin_correo():
        log.warning('[staging] correo NO enviado a %s | %s\n%s', destino, asunto, texto)
        return True

    if not configurado():
        log.error('Correo sin configurar: no se envió nada a %s', destino)
        return False

    cuerpo = {
        'from': _remitente(),
        'to': [destino],
        'subject': asunto,
        'text': texto,
    }
    if html:
        cuerpo['html'] = html

    peticion = urllib.request.Request(
        URL_RESEND, data=json.dumps(cuerpo).encode(), method='POST')
    peticion.add_header('Authorization', f"Bearer {os.environ['RESEND_API_KEY']}")
    peticion.add_header('Content-Type', 'application/json')
    return _pedir(peticion)


def url_absoluta(request, ruta):
    base = os.environ.get('SITE_URL', '').rstrip('/')
    if base:
        return f'{base}{ruta}'
    return request.build_absolute_uri(ruta)


def url_absoluta_sin_request(ruta):
    base = os.environ.get('SITE_URL', '').rstrip('/')
    return f'{base}{ruta}' if base else ruta
