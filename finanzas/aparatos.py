import hashlib
import logging
import secrets

from django.core import signing
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import correo

log = logging.getLogger('finanzas')

COOKIE = 'fintora_aparato'
SAL = 'finanzas.aparato'
DIAS_COOKIE = 400


def _huella(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _token_de(request):
    crudo = request.COOKIES.get(COOKIE, '')
    if not crudo:
        return ''
    try:
        return signing.loads(crudo, salt=SAL)
    except signing.BadSignature:
        return ''


def al_entrar(request, usuario):
    from . import auditoria
    from .models import DispositivoConocido, SesionActiva

    agente = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    token = _token_de(request)
    if token:
        filas = DispositivoConocido.objects.filter(usuario=usuario, huella=_huella(token))
        if filas.update(ultima_vez=timezone.now(), agente=agente):
            return False

    habia_otros = DispositivoConocido.objects.filter(usuario=usuario).exists()
    token = secrets.token_urlsafe(32)
    DispositivoConocido.objects.create(usuario=usuario, huella=_huella(token), agente=agente)
    request.cookie_aparato = signing.dumps(token, salt=SAL)

    if not habia_otros:
        return False

    aparato = SesionActiva(agente=agente).aparato
    auditoria.registrar('dispositivo_nuevo', request, usuario, detalle=aparato)
    destino = (usuario.email or '').strip()
    if destino:
        contexto = {
            'usuario': usuario,
            'aparato': aparato,
            'cuando': timezone.localtime(),
            'enlace': correo.url_absoluta(request, reverse('sesiones_activas')),
        }
        if not correo.enviar(destino, 'Nuevo acceso a tu cuenta de Fintora',
                             render_to_string('registration/correo_aparato.txt', contexto)):
            log.warning('No salió el aviso de aparato nuevo del usuario %s', usuario.pk)
    return True


def poner_cookie(request, respuesta, seguro):
    valor = getattr(request, 'cookie_aparato', '')
    if valor:
        respuesta.set_cookie(COOKIE, valor, max_age=DIAS_COOKIE * 86400,
                             httponly=True, secure=seguro, samesite='Lax')
    return respuesta
