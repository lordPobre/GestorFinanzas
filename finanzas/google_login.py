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
    return {'google_activo': bool(getattr(settings, 'GOOGLE_CLIENT_ID', ''))}


def _uri_retorno(request):
    uri = request.build_absolute_uri(reverse('google_listo'))
    if not settings.DEBUG and uri.startswith('http://'):
        uri = 'https://' + uri[len('http://'):]
    return uri


def _destino_seguro(valor):
    if valor and valor.startswith('/') and not valor.startswith('//'):
        return valor
    return ''


def entrar_google(request):
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
        'prompt': 'select_account',
    })
    return redirect(f'{URL_AUTORIZAR}?{parametros}')


@limitar(15, 3600, 'Demasiados intentos de acceso con Google. Prueba más tarde.')
def google_listo(request):
    estado_guardado = request.session.pop('google_estado', None)
    destino = _destino_seguro(request.session.pop('google_next', ''))

    if not estado_guardado or request.GET.get('state') != estado_guardado:
        messages.error(request, 'La sesión con Google no coincide. Vuelve a intentarlo.')
        return redirect('login')

    if request.GET.get('error') or not request.GET.get('code'):
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

    if SegundoFactor.objects.filter(usuario=usuario, activo=True).exists():
        request.session['2fa_pendiente'] = usuario.pk
        request.session['2fa_next'] = destino
        return redirect('verificar_codigo')

    request.metodo_acceso = 'google'
    login(request, usuario, backend=BACKEND)

    if recien_creado:
        messages.success(request, f'Cuenta creada con Google. Bienvenido, {usuario.username}.')

    return redirect(destino or 'dashboard')


def _canjear_codigo(codigo, uri_retorno):
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
    partes = id_token.split('.')
    if len(partes) != 3:
        raise ValueError('id_token mal formado')
    cuerpo = partes[1] + '=' * (-len(partes[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(cuerpo).decode('utf-8'))


def _validar(datos):
    if datos.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
        raise ValueError('emisor inesperado')
    if datos.get('aud') != settings.GOOGLE_CLIENT_ID:
        raise ValueError('el token no es de esta aplicación')
    if int(datos.get('exp', 0)) < time.time():
        raise ValueError('token vencido')
    if not datos.get('sub'):
        raise ValueError('falta el identificador de la cuenta')
    if not datos.get('email') or not datos.get('email_verified'):
        raise ValueError('correo no verificado por Google')


def _nombre_libre(correo):
    base = re.sub(r'[^a-z0-9._-]', '', correo.split('@')[0].lower())[:24] or 'usuario'
    nombre, n = base, 1
    while User.objects.filter(username__iexact=nombre).exists():
        n += 1
        nombre = f'{base}{n}'[:150]
    return nombre


def _usuario_para(datos):
    sub = datos['sub']
    correo = datos['email'].strip().lower()

    perfil = UserProfile.objects.filter(google_sub=sub).select_related('usuario').first()
    if perfil:
        return perfil.usuario, False

    usuario = (User.objects.filter(email__iexact=correo).first()
               or User.objects.filter(profile__email__iexact=correo).first())

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
    if not perfil.correo_verificado:
        from django.utils import timezone
        perfil.correo_verificado = True
        perfil.correo_verificado_en = timezone.now()
        campos += ['correo_verificado', 'correo_verificado_en']
    perfil.save(update_fields=campos)

    log.info('Acceso con Google: %s (%s)',
             usuario.username, 'cuenta nueva' if recien_creado else 'vinculada')
    return usuario, recien_creado
