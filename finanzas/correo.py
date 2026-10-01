import base64
import json
import logging
import os
import urllib.error
import urllib.request
from email.utils import formataddr, parseaddr
from pathlib import Path

from django.conf import settings

log = logging.getLogger('finanzas')

TIEMPO_ESPERA = 10
URL_RESEND = 'https://api.resend.com/emails'
AGENTE = 'Fintora/1.0 (+https://github.com/lordPobre/GestorFinanzas)'
NOMBRE_REMITENTE = 'Fintora'
URL_LOCAL = 'http://127.0.0.1:8000'

IMAGENES_EN_LINEA = {
    'fintora-cabecera': 'img/correo-cabecera.png',
}


def configurado():
    return bool(os.environ.get('RESEND_API_KEY'))


def _remitente():
    crudo = os.environ.get('CORREO_FROM') or settings.DEFAULT_FROM_EMAIL
    _, direccion = parseaddr(crudo)
    return formataddr((NOMBRE_REMITENTE, direccion or crudo))


def _staging_sin_correo():
    return bool(getattr(settings, 'ES_STAGING', False)
                and not getattr(settings, 'CORREO_EN_STAGING', False))


def _archivo_estatico(relativa):
    for carpeta in getattr(settings, 'STATICFILES_DIRS', []):
        ruta = Path(carpeta) / relativa
        if ruta.exists():
            return ruta
    raiz = getattr(settings, 'STATIC_ROOT', None)
    if raiz and (Path(raiz) / relativa).exists():
        return Path(raiz) / relativa
    return None


def _adjuntos_en_linea(html):
    adjuntos = []
    for cid, relativa in IMAGENES_EN_LINEA.items():
        if f'cid:{cid}' not in html:
            continue
        ruta = _archivo_estatico(relativa)
        if ruta is None:
            log.error('Falta la imagen del correo: %s', relativa)
            continue
        adjuntos.append({
            'filename': ruta.name,
            'content': base64.b64encode(ruta.read_bytes()).decode(),
            'content_id': cid,
        })
    return adjuntos


def cuerpo_resend(destino, asunto, texto, html=None):
    cuerpo = {
        'from': _remitente(),
        'to': [destino],
        'subject': asunto,
        'text': texto,
    }
    if html:
        cuerpo['html'] = html
        adjuntos = _adjuntos_en_linea(html)
        if adjuntos:
            cuerpo['attachments'] = adjuntos
    return cuerpo


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

    cuerpo = cuerpo_resend(destino, asunto, texto, html)
    peticion = urllib.request.Request(
        URL_RESEND, data=json.dumps(cuerpo).encode(), method='POST')
    peticion.add_header('Authorization', f"Bearer {os.environ['RESEND_API_KEY']}")
    peticion.add_header('Content-Type', 'application/json')
    return _pedir(peticion)


def url_absoluta(request, ruta):
    if settings.DEBUG and request is not None:
        return request.build_absolute_uri(ruta)
    base = os.environ.get('SITE_URL', '').rstrip('/')
    if base:
        return f'{base}{ruta}'
    return request.build_absolute_uri(ruta)


def url_absoluta_sin_request(ruta):
    if settings.DEBUG:
        base = os.environ.get('SITE_URL_LOCAL', URL_LOCAL).rstrip('/')
    else:
        base = os.environ.get('SITE_URL', '').rstrip('/')
    return f'{base}{ruta}' if base else ruta
