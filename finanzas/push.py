import base64
import json
import logging
import os
import struct
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('finanzas')

SERVICIOS = (
    'fcm.googleapis.com',
    'push.services.mozilla.com',
    'web.push.apple.com',
    'notify.windows.com',
)
TAMANO_REGISTRO = 4096
MAX_CARGA = 3000
SEGUNDOS_VIGENCIA = 12 * 60 * 60


def b64(datos):
    return base64.urlsafe_b64encode(datos).rstrip(b'=').decode('ascii')


def d64(texto):
    texto = (texto or '').strip()
    return base64.urlsafe_b64decode(texto + '=' * (-len(texto) % 4))


def _publica_cruda(clave_publica):
    return clave_publica.public_bytes(serialization.Encoding.X962,
                                      serialization.PublicFormat.UncompressedPoint)


def _privada():
    crudo = getattr(settings, 'VAPID_PRIVADA', '')
    if not crudo:
        return None
    try:
        return ec.derive_private_key(int.from_bytes(d64(crudo), 'big'), ec.SECP256R1())
    except (ValueError, TypeError):
        logger.error('VAPID_PRIVADA no es una clave válida.')
        return None


def disponible():
    return _privada() is not None


def clave_publica():
    privada = _privada()
    return b64(_publica_cruda(privada.public_key())) if privada else ''


def generar_claves():
    privada = ec.generate_private_key(ec.SECP256R1())
    valor = privada.private_numbers().private_value.to_bytes(32, 'big')
    return b64(valor), b64(_publica_cruda(privada.public_key()))


def endpoint_valido(url):
    if not isinstance(url, str) or len(url) > 500:
        return False
    try:
        partes = urlparse(url)
    except ValueError:
        return False
    host = (partes.hostname or '').lower()
    return (partes.scheme == 'https' and not partes.username and partes.port in (None, 443)
            and any(host == s or host.endswith('.' + s) for s in SERVICIOS))


def claves_validas(p256dh, auth):
    try:
        publica, secreto = d64(p256dh), d64(auth)
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), publica)
    except (ValueError, TypeError):
        return False
    return len(publica) == 65 and len(secreto) == 16 and len(p256dh) <= 120 and len(auth) <= 40


def cifrar(carga, p256dh, auth, efimera=None, sal=None):
    publica_ua = d64(p256dh)
    secreto = d64(auth)
    clave_ua = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), publica_ua)
    efimera = efimera or ec.generate_private_key(ec.SECP256R1())
    publica_as = _publica_cruda(efimera.public_key())
    compartido = efimera.exchange(ec.ECDH(), clave_ua)
    ikm = HKDF(hashes.SHA256(), 32, secreto,
               b'WebPush: info\x00' + publica_ua + publica_as).derive(compartido)
    sal = sal or os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, sal, b'Content-Encoding: aes128gcm\x00').derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, sal, b'Content-Encoding: nonce\x00').derive(ikm)
    cifrado = AESGCM(cek).encrypt(nonce, carga + b'\x02', None)
    return sal + struct.pack('!IB', TAMANO_REGISTRO, len(publica_as)) + publica_as + cifrado


def cabecera_vapid(endpoint, privada=None, ahora=None):
    privada = privada or _privada()
    partes = urlparse(endpoint)
    compacto = {'separators': (',', ':')}
    cabeza = b64(json.dumps({'typ': 'JWT', 'alg': 'ES256'}, **compacto).encode())
    reclamos = b64(json.dumps({
        'aud': f'{partes.scheme}://{partes.netloc}',
        'exp': int(ahora or time.time()) + SEGUNDOS_VIGENCIA,
        'sub': settings.VAPID_CONTACTO,
    }, **compacto).encode())
    firmado = f'{cabeza}.{reclamos}'
    r, s = decode_dss_signature(privada.sign(firmado.encode(), ec.ECDSA(hashes.SHA256())))
    firma = b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))
    publica = b64(_publica_cruda(privada.public_key()))
    return f'vapid t={firmado}.{firma}, k={publica}'


def _carga(datos):
    datos = {k: v for k, v in datos.items() if v}
    cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
    while len(cuerpo) > MAX_CARGA and datos.get('cuerpo'):
        datos['cuerpo'] = datos['cuerpo'][:max(0, len(datos['cuerpo']) - 200)]
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
    return cuerpo


def enviar(suscripcion, datos):
    privada = _privada()
    if privada is None:
        return 'error'
    if not endpoint_valido(suscripcion.endpoint):
        suscripcion.delete()
        return 'vencida'
    try:
        cuerpo = cifrar(_carga(datos), suscripcion.p256dh, suscripcion.auth)
    except (ValueError, TypeError):
        suscripcion.delete()
        return 'vencida'
    pedido = Request(suscripcion.endpoint, data=cuerpo, method='POST', headers={
        'Content-Encoding': 'aes128gcm',
        'Content-Type': 'application/octet-stream',
        'TTL': '43200',
        'Urgency': 'normal',
        'Authorization': cabecera_vapid(suscripcion.endpoint, privada),
    })
    try:
        with urlopen(pedido, timeout=10) as respuesta:
            estado = respuesta.status
    except HTTPError as e:
        estado = e.code
    except (URLError, TimeoutError, OSError) as e:
        logger.warning('Aviso push sin respuesta (%s)', type(e).__name__)
        return 'error'
    if estado in (404, 410):
        suscripcion.delete()
        return 'vencida'
    if 200 <= estado < 300:
        suscripcion.ultima_vez = timezone.now()
        suscripcion.save(update_fields=['ultima_vez'])
        return 'ok'
    logger.warning('El servicio de avisos devolvió %s', estado)
    return 'error'


def enviar_a_usuario(usuario, datos):
    return sum(1 for s in list(usuario.suscripciones_push.all()) if enviar(s, datos) == 'ok')
