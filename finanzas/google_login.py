"""Acceso con cuenta de Google (OAuth 2.0, flujo de servidor).

Por qué a mano y no con django-allauth: allauth trae sus propias URLs,
plantillas, modelos y flujo de sesión, y esta app ya tiene un acceso
propio con tope de intentos y verificación en dos pasos. Convivir con él
cuesta más que estas cien líneas.

Por qué el flujo de redirección y no el botón JavaScript de Google:
el botón de Google Identity Services necesita cargar un script y un
iframe de accounts.google.com, y la política de contenido de esta app
(finanzas/middleware.py) no los permite. Abrirla sería debilitar la
defensa contra XSS a cambio de nada: el flujo de redirección hace lo
mismo con un enlace normal, sin JavaScript, sin CDN y sin dependencias
nuevas — solo urllib, que viene con Python.

Qué pasa cuando alguien entra con Google:
  1. Se le manda a Google con un 'state' aleatorio guardado en su sesión.
  2. Google lo devuelve con un 'code'. Si el 'state' no coincide, se
     rechaza: es lo que impide que un tercero fabrique el retorno.
  3. El 'code' se canjea por un id_token en un POST directo a Google.
  4. Del id_token salen el correo y el 'sub' (identificador estable de la
     cuenta de Google, que no cambia aunque el usuario cambie de correo).
  5. Si ese 'sub' ya está vinculado, entra. Si no, se busca por correo y
     se vincula a la cuenta existente. Si tampoco, se crea una cuenta.
  6. Si la cuenta tiene verificación en dos pasos activa, igual se pide
     el código: Google confirma quién es, no reemplaza el segundo factor.
"""
import base64
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.crypto import get_random_string

from .models import SegundoFactor, UserProfile
from .seguridad import limitar

log = logging.getLogger('finanzas')

URL_AUTORIZAR = 'https://accounts.google.com/o/oauth2/v2/auth'
URL_TOKEN = 'https://oauth2.googleapis.com/token'
BACKEND = 'django.contrib.auth.backends.ModelBackend'


def google_disponible(request):
    """Context processor: la plantilla solo dibuja el botón si hay credenciales.

    Sin esto, en un equipo sin GOOGLE_CLIENT_ID el botón aparecería y
    llevaría a un error. Mejor que no exista.
    """
    return {'google_activo': bool(getattr(settings, 'GOOGLE_CLIENT_ID', ''))}


def _uri_retorno(request):
    """La dirección de vuelta.

    Tiene que ser idéntica byte a byte en la ida y en el canje, y estar
    registrada en Google Cloud Console. En producción se fuerza https:
    detrás del proxy de PythonAnywhere la petición llega como http y
    Google rechaza el retorno si no calzan.
    """
    uri = request.build_absolute_uri(reverse('google_listo'))
    if not settings.DEBUG and uri.startswith('http://'):
        uri = 'https://' + uri[len('http://'):]
    return uri


def _destino_seguro(valor):
    """Solo rutas internas. Un 'next' externo es una redirección abierta."""
    if valor and valor.startswith('/') and not valor.startswith('//'):
        return valor
    return ''


def entrar_google(request):
    """Paso 1: mandar al usuario a Google."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if not getattr(settings, 'GOOGLE_CLIENT_ID', ''):
        messages.error(request, 'El acceso con Google no está configurado.')
        return redirect('login')

    estado = get_random_string(32)
    request.session['google_estado'] = estado
    request.session['google_next'] = _destino_seguro(request.GET.get('next'))

    parametros = urllib.parse.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': _uri_retorno(request),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': estado,
        # Que muestre el selector: en un equipo compartido, sin esto entra
        # con la última cuenta usada sin preguntar.
        'prompt': 'select_account',
    })
    return redirect(f'{URL_AUTORIZAR}?{parametros}')


@limitar(15, 3600, 'Demasiados intentos de acceso con Google. Prueba más tarde.')
def google_listo(request):
    """Paso 2: Google devuelve al usuario acá con un código."""
    estado_guardado = request.session.pop('google_estado', None)
    destino = _destino_seguro(request.session.pop('google_next', ''))

    if not estado_guardado or request.GET.get('state') != estado_guardado:
        # Sin 'state' válido no se sabe si el retorno lo pidió este usuario.
        messages.error(request, 'La sesión con Google no coincide. Vuelve a intentarlo.')
        return redirect('login')

    if request.GET.get('error') or not request.GET.get('code'):
        # Caso normal: el usuario apretó "Cancelar" en la pantalla de Google.
        messages.error(request, 'No se completó el acceso con Google.')
        return redirect('login')

    try:
        respuesta = _canjear_codigo(request.GET['code'], _uri_retorno(request))
        datos = _leer_id_token(respuesta.get('id_token', ''))
        _validar(datos)
    except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError) as e:
        log.warning('Acceso con Google fallido: %s', e)
        messages.error(request, 'No se pudo verificar tu cuenta de Google.')
        return redirect('login')

    usuario, recien_creado = _usuario_para(datos)

    if not usuario.is_active:
        messages.error(request, 'Esta cuenta está desactivada.')
        return redirect('login')

    # El segundo factor se pide igual. Google acredita el correo; el código
    # acredita que quien entra tiene además el teléfono del dueño.
    if SegundoFactor.objects.filter(usuario=usuario, activo=True).exists():
        request.session['2fa_pendiente'] = usuario.pk
        request.session['2fa_next'] = destino
        return redirect('verificar_codigo')

    # backend explícito: login() lo necesita porque no pasamos por
    # authenticate(), y sin él Django levanta ValueError en cuanto haya más
    # de un backend configurado.
    login(request, usuario, backend=BACKEND)

    if recien_creado:
        messages.success(request, f'Cuenta creada con Google. Bienvenido, {usuario.username}.')

    return redirect(destino or 'dashboard')


# ------------------------------------------------------------------
#  Piezas internas
# ------------------------------------------------------------------

def _canjear_codigo(codigo, uri_retorno):
    """Cambia el código de un solo uso por el id_token, hablando con Google."""
    cuerpo = urllib.parse.urlencode({
        'code': codigo,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': uri_retorno,
        'grant_type': 'authorization_code',
    }).encode()

    pedido = urllib.request.Request(URL_TOKEN, data=cuerpo, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(pedido, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def _leer_id_token(id_token):
    """Saca los datos del id_token.

    No se verifica la firma a propósito, y es seguro acá: el token no viene
    del navegador sino de un POST nuestro a oauth2.googleapis.com por TLS.
    La propia documentación de Google permite omitir la validación de firma
    en este caso. Lo que sí se comprueba, abajo, es que el contenido sea el
    esperado. Si algún día el token llegara por el navegador (flujo con
    JavaScript), esto ya no bastaría y habría que verificar la firma.
    """
    partes = id_token.split('.')
    if len(partes) != 3:
        raise ValueError('id_token mal formado')
    cuerpo = partes[1] + '=' * (-len(partes[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(cuerpo).decode('utf-8'))


def _validar(datos):
    if datos.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise ValueError('emisor inesperado')
    if datos.get('aud') != settings.GOOGLE_CLIENT_ID:
        # El token es de otra aplicación: aceptarlo dejaría entrar con un
        # token conseguido en cualquier otro sitio.
        raise ValueError('el token no es de esta aplicación')
    if int(datos.get('exp', 0)) < time.time():
        raise ValueError('token vencido')
    if not datos.get('sub'):
        raise ValueError('falta el identificador de la cuenta')
    if not datos.get('email') or not datos.get('email_verified'):
        # Sin correo verificado no se puede vincular por correo sin abrir la
        # puerta a que alguien reclame la cuenta de otro.
        raise ValueError('correo no verificado por Google')


def _nombre_libre(correo):
    base = re.sub(r'[^a-z0-9._-]', '', correo.split('@')[0].lower())[:24] or 'usuario'
    nombre, n = base, 1
    while User.objects.filter(username__iexact=nombre).exists():
        n += 1
        nombre = f'{base}{n}'[:150]
    return nombre


def _usuario_para(datos):
    """Devuelve (usuario, recien_creado) para esta cuenta de Google."""
    sub = datos['sub']
    correo = datos['email'].strip().lower()

    # 1. Ya entró con Google antes.
    perfil = UserProfile.objects.filter(google_sub=sub).select_related('usuario').first()
    if perfil:
        return perfil.usuario, False

    # 2. Ya tenía cuenta con ese correo: se vincula y entra a la de siempre,
    #    con sus gastos y su historial. Solo vale porque Google verificó el
    #    correo (lo comprueba _validar).
    usuario = (User.objects.filter(email__iexact=correo).first()
               or User.objects.filter(profile__email__iexact=correo).first())

    # 3. Nadie: cuenta nueva, sin contraseña utilizable. Entra por Google o
    #    por "¿La olvidaste?", que le deja poner una.
    recien_creado = usuario is None
    if recien_creado:
        usuario = User.objects.create(
            username=_nombre_libre(correo),
            email=correo,
            first_name=(datos.get('given_name') or '')[:30],
            last_name=(datos.get('family_name') or '')[:150],
        )
        usuario.set_unusable_password()
        usuario.save(update_fields=['password'])

    perfil, _ = UserProfile.objects.get_or_create(usuario=usuario)
    perfil.google_sub = sub
    campos = ['google_sub']
    if not perfil.email:
        perfil.email = correo
        campos.append('email')
    if not perfil.nombre_completo and datos.get('name'):
        perfil.nombre_completo = datos['name'][:100]
        campos.append('nombre_completo')
    perfil.save(update_fields=campos)

    log.info('Acceso con Google: %s (%s)',
             usuario.username, 'cuenta nueva' if recien_creado else 'vinculada')
    return usuario, recien_creado
