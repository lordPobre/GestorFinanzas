import hashlib
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

log = logging.getLogger('finanzas')

URL = 'https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_64'
MODELO_POR_DEFECTO = 'eleven_multilingual_v2'
MAX_CARACTERES = 900
SEGUNDOS_EN_CACHE = 6 * 3600
TIEMPO_ESPERA = 15


def configurada():
    return bool(os.environ.get('ELEVENLABS_API_KEY', '').strip()
                and os.environ.get('ELEVENLABS_VOZ', '').strip())


def _modelo():
    return os.environ.get('ELEVENLABS_MODELO', '').strip() or MODELO_POR_DEFECTO


def sintetizar(texto):
    texto = ' '.join((texto or '').split())[:MAX_CARACTERES]
    if not texto or not configurada():
        return None

    voz = os.environ['ELEVENLABS_VOZ'].strip()
    modelo = _modelo()
    clave = 'voz:' + hashlib.sha256(f'{voz}|{modelo}|{texto}'.encode()).hexdigest()
    guardado = cache.get(clave)
    if guardado:
        return guardado

    cuerpo = {
        'text': texto,
        'model_id': modelo,
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.15,
                           'use_speaker_boost': True},
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
        cache.set(clave, audio, SEGUNDOS_EN_CACHE)
    return audio or None
