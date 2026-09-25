import logging

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from . import correo, legal
from .models import UserProfile

log = logging.getLogger('finanzas')

MESES = legal.MESES_INACTIVIDAD
DIAS_GRACIA = legal.DIAS_GRACIA_INACTIVIDAD


def ultima_senal(usuario, perfil=None):
    candidatos = [usuario.last_login, usuario.date_joined]
    if perfil is not None:
        candidatos.append(perfil.ultima_actividad)
    fechas = [f for f in candidatos if f]
    return max(fechas) if fechas else None


def dias_inactivo(usuario, perfil=None, ahora=None):
    senal = ultima_senal(usuario, perfil)
    if not senal:
        return 0
    return ((ahora or timezone.now()) - senal).days


def _perfil(usuario):
    perfil = getattr(usuario, 'profile', None)
    if perfil is None:
        perfil, _ = UserProfile.objects.get_or_create(usuario=usuario)
    return perfil


def _cuentas(usuario=None):
    cuentas = (User.objects.filter(is_active=True, is_superuser=False)
               .select_related('profile'))
    if usuario:
        cuentas = cuentas.filter(username=usuario)
    return cuentas


def por_avisar(ahora=None, usuario=None):
    ahora = ahora or timezone.now()
    tope = ahora - relativedelta(months=MESES)

    candidatas = _cuentas(usuario).filter(
        Q(profile__ultima_actividad__lt=tope) | Q(profile__ultima_actividad__isnull=True),
        Q(last_login__lt=tope) | Q(last_login__isnull=True),
        date_joined__lt=tope,
    )

    salida = []
    for cuenta in candidatas:
        perfil = _perfil(cuenta)
        if perfil.aviso_inactividad_enviado:
            continue
        if ultima_senal(cuenta, perfil) < tope:
            salida.append((cuenta, perfil))
    return salida


def por_borrar(ahora=None, usuario=None):
    ahora = ahora or timezone.now()
    corte = ahora - relativedelta(days=DIAS_GRACIA)

    candidatas = (_cuentas(usuario)
                  .filter(profile__aviso_inactividad_enviado__lt=corte))

    salida = []
    for cuenta in candidatas:
        perfil = _perfil(cuenta)
        if ultima_senal(cuenta, perfil) > perfil.aviso_inactividad_enviado:
            perfil.aviso_inactividad_enviado = None
            perfil.save(update_fields=['aviso_inactividad_enviado'])
            continue
        salida.append((cuenta, perfil))
    return salida


def destinatario(usuario, perfil=None):
    if usuario.email:
        return usuario.email
    perfil = perfil if perfil is not None else _perfil(usuario)
    return perfil.email or ''


def avisar(usuario, perfil=None, ahora=None):
    perfil = perfil if perfil is not None else _perfil(usuario)
    destino = destinatario(usuario, perfil)
    if not destino:
        log.warning('Cuenta inactiva %s sin correo: no se puede avisar', usuario.pk)
        return False

    contexto = {
        'usuario': usuario,
        'meses': MESES,
        'dias': DIAS_GRACIA,
        'enlace': correo.url_absoluta_sin_request('/login/'),
    }
    ok = correo.enviar(
        destino,
        'Tu cuenta de Rekon se va a borrar por inactividad',
        render_to_string('finanzas/correo_inactividad.txt', contexto),
        render_to_string('finanzas/correo_inactividad.html', contexto),
    )
    if not ok:
        return False

    perfil.aviso_inactividad_enviado = ahora or timezone.now()
    perfil.save(update_fields=['aviso_inactividad_enviado'])
    log.info('Aviso de inactividad enviado al usuario %s', usuario.pk)
    return True


def borrar(usuario, perfil=None):
    uid, nombre = usuario.pk, usuario.get_username()
    dias = dias_inactivo(usuario, perfil)
    usuario.delete()
    log.warning('Cuenta borrada por inactividad: id=%s usuario=%s dias=%s',
                uid, nombre, dias)
