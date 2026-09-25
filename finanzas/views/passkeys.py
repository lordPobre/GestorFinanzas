import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from webauthn import (generate_authentication_options, generate_registration_options,
                      options_to_json, verify_authentication_response,
                      verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria,
                                      PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement,
                                      UserVerificationRequirement)

from .. import auditoria
from ..models import Passkey, SegundoFactor
from ..seguridad import _ip, esta_bloqueado, limitar, limpiar_intentos, registrar_fallo
from .comun import contadores

logger = logging.getLogger('finanzas')

RP_NOMBRE = 'Rekon'
CLAVE_BLOQUEO = ''
BACKEND = 'django.contrib.auth.backends.ModelBackend'


def _rp_id(request):
    return getattr(settings, 'WEBAUTHN_RP_ID', '') or request.get_host().split(':')[0]


def _origen(request):
    return f'{request.scheme}://{request.get_host()}'


def _handle(usuario):
    return hmac.new(settings.SECRET_KEY.encode(), f'passkey:{usuario.pk}'.encode(),
                    hashlib.sha256).digest()


def _nombre_aparato(request):
    ua = request.META.get('HTTP_USER_AGENT', '')
    for marca, nombre in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Android'),
                          ('Macintosh', 'Mac'), ('Windows', 'Windows')):
        if marca in ua:
            return nombre
    return 'Este dispositivo'


def _destino(texto):
    if texto and texto.startswith('/') and not texto.startswith('//'):
        return texto
    return reverse('dashboard')


def _error(texto, estado=400):
    return JsonResponse({'ok': False, 'msg': texto}, status=estado)


@login_required(login_url='/login/')
def passkeys(request):
    if request.method == 'POST' and request.POST.get('accion') == 'eliminar':
        borradas, _ = Passkey.objects.filter(usuario=request.user,
                                             pk=request.POST.get('id')).delete()
        if borradas:
            auditoria.registrar('passkey_quitada', request)
            messages.success(request, 'Ese dispositivo ya no puede entrar con Face ID o huella.')
        return redirect('passkeys')

    contexto = {
        'passkeys': Passkey.objects.filter(usuario=request.user),
        'pide_password': request.user.has_usable_password(),
        'tiene_2fa': SegundoFactor.objects.filter(usuario=request.user, activo=True).exists(),
        'nombre_sugerido': _nombre_aparato(request),
    }
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/passkeys.html', contexto)


@login_required(login_url='/login/')
@require_POST
@limitar(10, 3600, 'Demasiados intentos. Prueba de nuevo en un rato.')
def registro_opciones(request):
    usuario = request.user
    if usuario.has_usable_password() and not usuario.check_password(request.POST.get('password', '')):
        return _error('Contraseña incorrecta.')

    existentes = [PublicKeyCredentialDescriptor(id=base64url_to_bytes(p.credencial_id))
                  for p in usuario.passkeys.all()]
    opciones = generate_registration_options(
        rp_id=_rp_id(request),
        rp_name=RP_NOMBRE,
        user_id=_handle(usuario),
        user_name=usuario.email or usuario.username,
        user_display_name=usuario.get_full_name() or usuario.username,
        exclude_credentials=existentes,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        timeout=60000,
    )
    request.session['passkey_registro'] = bytes_to_base64url(opciones.challenge)
    return JsonResponse({'ok': True, 'opciones': json.loads(options_to_json(opciones))})


@login_required(login_url='/login/')
@require_POST
def registro_verificar(request):
    reto = request.session.pop('passkey_registro', None)
    if not reto:
        return _error('La solicitud expiró. Vuelve a intentarlo.')

    try:
        verificado = verify_registration_response(
            credential=request.POST.get('credencial', ''),
            expected_challenge=base64url_to_bytes(reto),
            expected_origin=_origen(request),
            expected_rp_id=_rp_id(request),
            require_user_verification=True,
        )
    except Exception as exc:
        logger.info('Registro de passkey rechazado: %s', exc)
        return _error('No se pudo vincular este dispositivo. Vuelve a intentarlo.')

    credencial_id = bytes_to_base64url(verificado.credential_id)
    if Passkey.objects.filter(credencial_id=credencial_id).exists():
        return _error('Este dispositivo ya estaba vinculado.')

    nombre = (request.POST.get('nombre') or '').strip()[:60] or _nombre_aparato(request)
    Passkey.objects.create(
        usuario=request.user,
        credencial_id=credencial_id,
        clave_publica=bytes_to_base64url(verificado.credential_public_key),
        contador=verificado.sign_count,
        nombre=nombre,
    )
    auditoria.registrar('passkey_agregada', request, detalle=nombre)
    messages.success(request, 'Listo. La próxima vez puedes entrar con Face ID o huella.')
    return JsonResponse({'ok': True})


@require_POST
@limitar(30, 900, 'Demasiados intentos. Entra con tu contraseña.')
def entrar_opciones(request):
    opciones = generate_authentication_options(
        rp_id=_rp_id(request),
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=60000,
    )
    request.session['passkey_reto'] = bytes_to_base64url(opciones.challenge)
    return JsonResponse({'ok': True, 'opciones': json.loads(options_to_json(opciones))})


@require_POST
def entrar_verificar(request):
    ip = _ip(request)
    restan = esta_bloqueado(CLAVE_BLOQUEO, ip)
    if restan:
        return _error(f'Demasiados intentos. Espera {max(1, restan // 60)} minutos '
                      'o entra con tu contraseña.', 429)

    reto = request.session.pop('passkey_reto', None)
    if not reto:
        return _error('La solicitud expiró. Vuelve a intentarlo.')

    try:
        datos = json.loads(request.POST.get('credencial', ''))
        passkey = Passkey.objects.select_related('usuario').get(
            credencial_id=datos.get('rawId') or datos.get('id'))
    except (ValueError, AttributeError, Passkey.DoesNotExist):
        registrar_fallo(CLAVE_BLOQUEO, ip)
        auditoria.registrar('passkey_fallida', request, detalle='credencial desconocida')
        return _error('Este dispositivo no está vinculado a ninguna cuenta. '
                      'Entra con tu contraseña.')

    usuario = passkey.usuario
    try:
        verificado = verify_authentication_response(
            credential=datos,
            expected_challenge=base64url_to_bytes(reto),
            expected_rp_id=_rp_id(request),
            expected_origin=_origen(request),
            credential_public_key=base64url_to_bytes(passkey.clave_publica),
            credential_current_sign_count=passkey.contador,
            require_user_verification=True,
        )
        handle = (datos.get('response') or {}).get('userHandle')
        if handle and not hmac.compare_digest(base64url_to_bytes(handle), _handle(usuario)):
            raise ValueError('userHandle no coincide')
    except Exception as exc:
        logger.info('Acceso con passkey rechazado: %s', exc)
        registrar_fallo(CLAVE_BLOQUEO, ip)
        auditoria.registrar('passkey_fallida', request, usuario, detalle='firma rechazada')
        return _error('No pudimos reconocerte. Entra con tu contraseña.')

    if not usuario.is_active:
        return _error('Esta cuenta está desactivada.')

    passkey.contador = verificado.new_sign_count
    passkey.ultimo_uso = timezone.now()
    passkey.save(update_fields=['contador', 'ultimo_uso'])
    limpiar_intentos(CLAVE_BLOQUEO, ip)

    request.metodo_acceso = 'face_id_o_huella'
    login(request, usuario, backend=BACKEND)
    return JsonResponse({'ok': True, 'destino': _destino(request.POST.get('next', ''))})
