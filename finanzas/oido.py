import json
import logging
import os
import urllib.error
import urllib.request
import uuid

from .voz import configurada

log = logging.getLogger('finanzas')

URL = 'https://api.elevenlabs.io/v1/speech-to-text'
MODELO_POR_DEFECTO = 'scribe_v2'
MAX_BYTES = 2 * 1024 * 1024
MIN_BYTES = 1000
TIPOS = ('audio/webm', 'audio/ogg', 'audio/mp4', 'audio/aac', 'audio/mpeg', 'audio/wav', 'audio/x-wav')
TIEMPO_ESPERA = 20


def _modelo():
    return os.environ.get('ELEVENLABS_MODELO_OIDO', '').strip() or MODELO_POR_DEFECTO


def tipo_base(tipo):
    return (tipo or '').split(';')[0].strip().lower()


def _cuerpo(campos, audio, tipo):
    limite = uuid.uuid4().hex
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in campos.items()]
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="file"; filename="pregunta"\r\n'
                  f'Content-Type: {tipo}\r\n\r\n'.encode() + audio + b'\r\n')
    partes.append(f'--{limite}--\r\n'.encode())
    return b''.join(partes), f'multipart/form-data; boundary={limite}'


def transcribir(audio, tipo):
    if not audio or not configurada():
        return None

    campos = {'model_id': _modelo(), 'language_code': 'spa', 'tag_audio_events': 'false',
              'diarize': 'false', 'timestamps_granularity': 'none'}
    cuerpo, tipo_cuerpo = _cuerpo(campos, audio, tipo_base(tipo))
    pedido = urllib.request.Request(URL, data=cuerpo, method='POST')
    pedido.add_header('xi-api-key', os.environ['ELEVENLABS_API_KEY'].strip())
    pedido.add_header('Content-Type', tipo_cuerpo)
    pedido.add_header('Accept', 'application/json')
    pedido.add_header('User-Agent', 'Fintora')
    try:
        with urllib.request.urlopen(pedido, timeout=TIEMPO_ESPERA) as respuesta:
            datos = json.loads(respuesta.read())
    except urllib.error.HTTPError as e:
        log.error('ElevenLabs no transcribió (%s): %s', e.code, e.read().decode(errors='replace')[:200])
        return None
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.error('No se pudo transcribir con ElevenLabs: %s', e)
        return None

    texto = ' '.join(str((datos or {}).get('text') or '').split())
    return texto if any(c.isalnum() for c in texto) else ''
