import logging
from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.utils import timezone

log = logging.getLogger('finanzas')

DIAS_CONSERVACION = 365


def _ip(request):
    if request is None:
        return None
    from .sesiones import _ip_valida
    return _ip_valida(request)


def _agente(request):
    if request is None:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:300]


def registrar(tipo, request=None, usuario=None, referencia='', detalle=''):
    from .models import EventoSeguridad

    if usuario is None and request is not None:
        actual = getattr(request, 'user', None)
        if actual is not None and actual.is_authenticated:
            usuario = actual
    if usuario is not None and not getattr(usuario, 'pk', None):
        usuario = None
    referencia = (referencia or (usuario.get_username() if usuario else ''))[:150]

    log.info('seguridad tipo=%s usuario=%s ref=%s ip=%s',
             tipo, getattr(usuario, 'pk', '-'), referencia or '-', _ip(request) or '-')
    try:
        EventoSeguridad.objects.create(
            tipo=tipo, usuario=usuario, referencia=referencia,
            ip=_ip(request), agente=_agente(request), detalle=(detalle or '')[:300],
        )
    except Exception:
        log.warning('No se pudo guardar el evento de seguridad %s', tipo, exc_info=True)


def purgar(ahora=None):
    from .models import EventoSeguridad
    limite = (ahora or timezone.now()) - timedelta(days=DIAS_CONSERVACION)
    borrados, _ = EventoSeguridad.objects.filter(creado__lt=limite).delete()
    return borrados


@receiver(user_logged_in)
def _al_entrar(sender, request, user, **kwargs):
    registrar('acceso', request, user, detalle=getattr(request, 'metodo_acceso', 'contraseña'))


@receiver(user_logged_out)
def _al_salir(sender, request, user, **kwargs):
    if user is not None:
        registrar('salida', request, user)


@receiver(user_login_failed)
def _al_fallar(sender, credentials, request=None, **kwargs):
    registrar('acceso_fallido', request, None,
              referencia=(credentials or {}).get('username', ''), detalle='contraseña')
