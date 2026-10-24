import hashlib
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone

from .habla import para_voz

log = logging.getLogger('finanzas')

URL = 'https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_64'
MODELO_POR_DEFECTO = 'eleven_multilingual_v2'
MAX_CARACTERES = 1200
VELOCIDAD_POR_DEFECTO = 0.9
SEGUNDOS_EN_CACHE = 6 * 3600
VIDA_EN_R2 = timedelta(hours=5)
CARPETA = 'voz'
TIEMPO_ESPERA = 15


def configurada():
    return bool(os.environ.get('ELEVENLABS_API_KEY', '').strip()
                and os.environ.get('ELEVENLABS_VOZ', '').strip())


def _modelo():
    return os.environ.get('ELEVENLABS_MODELO', '').strip() or MODELO_POR_DEFECTO


def _velocidad():
    try:
        valor = float(os.environ.get('ELEVENLABS_VELOCIDAD', '').strip() or VELOCIDAD_POR_DEFECTO)
    except ValueError:
        valor = VELOCIDAD_POR_DEFECTO
    return min(1.2, max(0.7, valor))


def _almacen():
    from .almacenamiento import almacen_media, r2_configurado
    return almacen_media if r2_configurado() else None


def _ruta(huella):
    return f'{CARPETA}/{huella}.mp3'


def _vencido(almacen, ruta):
    return timezone.now() - almacen.get_modified_time(ruta) > VIDA_EN_R2


def _leer(huella):
    almacen = _almacen()
    if almacen is None:
        return cache.get('voz:' + huella)
    ruta = _ruta(huella)
    try:
        if not almacen.exists(ruta):
            return None
        if _vencido(almacen, ruta):
            almacen.delete(ruta)
            return None
        with almacen.open(ruta, 'rb') as archivo:
            return archivo.read()
    except Exception:
        log.warning('No se pudo leer el audio guardado %s', ruta, exc_info=True)
        return None


def _guardar(huella, audio):
    almacen = _almacen()
    if almacen is None:
        cache.set('voz:' + huella, audio, SEGUNDOS_EN_CACHE)
        return
    ruta = _ruta(huella)
    try:
        if almacen.exists(ruta):
            almacen.delete(ruta)
        almacen.save(ruta, ContentFile(audio))
    except Exception:
        log.warning('No se pudo guardar el audio %s', ruta, exc_info=True)


def limpiar_audios():
    almacen = _almacen()
    if almacen is None:
        return 0
    try:
        _, archivos = almacen.listdir(CARPETA)
    except FileNotFoundError:
        return 0
    borrados = 0
    for nombre in archivos:
        ruta = f'{CARPETA}/{nombre}'
        try:
            if _vencido(almacen, ruta):
                almacen.delete(ruta)
                borrados += 1
        except Exception:
            log.warning('No se pudo revisar el audio %s', ruta, exc_info=True)
    return borrados


def sintetizar(texto):
    texto = para_voz(' '.join((texto or '').split()))[:MAX_CARACTERES]
    if not texto or not configurada():
        return None

    voz = os.environ['ELEVENLABS_VOZ'].strip()
    modelo = _modelo()
    velocidad = _velocidad()
    huella = hashlib.sha256(f'{voz}|{modelo}|{velocidad:g}|{texto}'.encode()).hexdigest()
    guardado = _leer(huella)
    if guardado:
        return guardado

    cuerpo = {
        'text': texto,
        'model_id': modelo,
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.15,
                           'use_speaker_boost': True, 'speed': velocidad},
    }
    pedido = urllib.request.Request(URL.format(voz=urllib.parse.quote(voz, safe='')),
                                    data=json.dumps(cuerpo).encode(), method='POST')
    pedido.add_header('xi-api-key', os.environ['ELEVENLABS_API_KEY'].strip())
    pedido.add_header('Content-Type', 'application/json')
    pedido.add_header('Accept', 'audio/mpeg')
    pedido.add_header('User-Agent', 'Fintora')
    try:
        with urllib.request.urlopen(pedido, timeout=TIEMPO_ESPERA) as respuesta:
            audio = respuesta.read()
    except urllib.error.HTTPError as e:
        log.error('ElevenLabs devolvió %s: %s', e.code, e.read().decode(errors='replace')[:200])
        return None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.error('No se pudo hablar con ElevenLabs: %s', e)
        return None

    if audio:
        _guardar(huella, audio)
    return audio or None
