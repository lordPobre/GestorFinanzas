"""Envío de correo por API HTTP (Resend o Mailgun).

Por qué HTTP y no SMTP: PythonAnywhere en cuenta gratuita solo deja salir
por HTTP(S) a los sitios de su lista blanca. Un envío por SMTP (puertos 587
o 465) queda bloqueado antes de salir, así que el backend de correo normal
de Django no sirve ahí. Una API HTTPS pasa por el mismo camino que
cualquier otra petición.

Soporta los dos proveedores a propósito: api.resend.com es más nuevo y
puede no estar en la lista blanca de PythonAnywhere todavía, mientras
api.mailgun.net lleva años en ella. Si uno no sale, se cambia una variable
de entorno en vez de reescribir esto.

Se elige con PROVEEDOR_CORREO ('resend' o 'mailgun'). Si no está definida,
se usa el que tenga credenciales, con Resend primero.

Resend:
  RESEND_API_KEY    la clave (re_...)
  CORREO_FROM       remitente, ej: FinApp <no-responder@tudominio.dev>

Mailgun:
  MAILGUN_API_KEY   clave privada o sending key
  MAILGUN_DOMAIN    dominio verificado (o el sandbox)
  MAILGUN_FROM      remitente (CORREO_FROM también vale)
  MAILGUN_BASE      opcional: https://api.eu.mailgun.net si la cuenta es europea

Común:
  SITE_URL          base de los enlaces que van en el correo

Si falta lo necesario, enviar() no revienta: registra el error y devuelve
False. La vista que llama decide qué contarle al usuario.
"""
import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger('finanzas')

TIEMPO_ESPERA = 10  # segundos


def proveedor():
    """Cuál de los dos se va a usar, o None si ninguno está listo."""
    elegido = (os.environ.get('PROVEEDOR_CORREO') or '').strip().lower()
    if elegido in ('resend', 'mailgun'):
        return elegido
    if os.environ.get('RESEND_API_KEY'):
        return 'resend'
    if os.environ.get('MAILGUN_API_KEY') and os.environ.get('MAILGUN_DOMAIN'):
        return 'mailgun'
    return None


def configurado():
    """Hay credenciales suficientes para enviar."""
    p = proveedor()
    if p == 'resend':
        return bool(os.environ.get('RESEND_API_KEY'))
    if p == 'mailgun':
        return bool(os.environ.get('MAILGUN_API_KEY')
                    and os.environ.get('MAILGUN_DOMAIN'))
    return False


def _remitente():
    directo = os.environ.get('CORREO_FROM') or os.environ.get('MAILGUN_FROM')
    if directo:
        return directo
    dominio = os.environ.get('MAILGUN_DOMAIN', 'localhost')
    return f'FinApp <no-responder@{dominio}>'


def _pedir(peticion):
    """Lanza la petición y devuelve True si el proveedor la aceptó."""
    # User-Agent propio: urllib se identifica como "Python-urllib/3.x" y
    # Cloudflare — que está delante de la API de Resend — lo rechaza con un
    # 403 y el código 1010 ("firma de navegador bloqueada") antes de que la
    # petición llegue al servicio.
    peticion.add_header('User-Agent', 'FinApp/1.0 (+https://github.com/lordPobre/GestorFinanzas)')
    peticion.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA) as respuesta:
            cuerpo = json.loads(respuesta.read().decode() or '{}')
            log.info('Correo aceptado: %s', cuerpo.get('id', 'sin id'))
            return True
    except urllib.error.HTTPError as e:
        # 401/403 son de configuración, no de red: clave mal, dominio sin
        # verificar, o cuenta de pruebas que solo envía a direcciones
        # autorizadas. El cuerpo de la respuesta lo dice con claridad.
        log.error('El proveedor de correo devolvió %s: %s',
                  e.code, e.read().decode()[:300])
    except Exception as e:
        log.error('No se pudo hablar con el proveedor de correo: %s', e)
    return False


def _enviar_resend(destino, asunto, texto, html=None):
    cuerpo = {
        'from': _remitente(),
        'to': [destino],
        'subject': asunto,
        'text': texto,
    }
    if html:
        cuerpo['html'] = html
    datos = json.dumps(cuerpo).encode()

    peticion = urllib.request.Request(
        'https://api.resend.com/emails', data=datos, method='POST')
    peticion.add_header('Authorization', f"Bearer {os.environ['RESEND_API_KEY']}")
    peticion.add_header('Content-Type', 'application/json')
    return _pedir(peticion)


def _enviar_mailgun(destino, asunto, texto, html=None):
    base = os.environ.get('MAILGUN_BASE', 'https://api.mailgun.net').rstrip('/')
    url = f"{base}/v3/{os.environ['MAILGUN_DOMAIN']}/messages"

    campos = {
        'from': _remitente(),
        'to': destino,
        'subject': asunto,
        'text': texto,
    }
    if html:
        campos['html'] = html
    datos = urllib.parse.urlencode(campos).encode()

    # Autenticación básica: usuario 'api', contraseña la clave.
    credencial = base64.b64encode(
        f"api:{os.environ['MAILGUN_API_KEY']}".encode()).decode()

    peticion = urllib.request.Request(url, data=datos, method='POST')
    peticion.add_header('Authorization', f'Basic {credencial}')
    peticion.add_header('Content-Type', 'application/x-www-form-urlencoded')
    return _pedir(peticion)


def enviar(destino, asunto, texto, html=None):
    """Manda un correo. Devuelve True si fue aceptado.

    Los dos cuerpos viajan juntos: 'texto' y, si se pasa, 'html'. El cliente
    de correo elige cuál muestra — el HTML normalmente, el texto plano si
    bloquea imágenes y estilos o si es un lector de pantalla. Mandar solo
    HTML deja a esos casos con un correo vacío.
    """
    p = proveedor()
    if not configurado():
        log.error('Correo sin configurar: no se envió nada a %s', destino)
        return False
    if p == 'resend':
        return _enviar_resend(destino, asunto, texto, html)
    return _enviar_mailgun(destino, asunto, texto, html)


def url_absoluta(request, ruta):
    """La URL completa para un enlace de correo.

    SITE_URL manda si está definida: detrás del proxy de PythonAnywhere,
    build_absolute_uri puede armar la dirección con http en vez de https.
    """
    base = os.environ.get('SITE_URL', '').rstrip('/')
    if base:
        return f'{base}{ruta}'
    return request.build_absolute_uri(ruta)
