"""Borrado de cuentas inactivas: aviso a los 12 meses, borrado 30 días después.

Guardar datos financieros de alguien que no vuelve no tiene justificación: la
finalidad por la que los entregó —llevar sus cuentas— dejó de existir. La
política de privacidad ya lo promete; esto es lo que lo cumple.

El plazo se cuenta desde la última señal de vida real, que es el máximo de
tres fechas: la actividad que anota el middleware, el último login y el alta.
No basta con last_login — quien deja la sesión abierta en su teléfono no
vuelve a pasar por login() y su last_login queda congelado, así que una
cuenta de uso diario parecería abandonada.

Nunca se borra sin avisar. Al cruzar los 12 meses sale un correo y se anota
la fecha del envío; el borrado ocurre 30 días después de ESE correo, no de la
inactividad. Si la persona entra en el medio, su actividad pasa a ser más
reciente que el aviso y el proceso se cancela solo: el campo se limpia y
vuelve a empezar de cero.

Si el correo no se puede enviar —no hay dirección, o el proveedor lo
rechaza— la cuenta no se marca y por lo tanto no se borra. Un borrado
silencioso por un fallo de correo sería justo el error que no se puede
deshacer.
"""
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
    """La fecha más reciente en que la cuenta dio señales de vida."""
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
    """Cuentas que cruzaron el plazo y todavía no recibieron el aviso.

    El filtro grueso lo hace la base sobre las tres fechas; el fino, Python
    sobre el máximo de ellas. Así no se recorre la tabla entera, y el máximo
    —que la base no puede calcular entre columnas de dos tablas sin
    complicarse— se resuelve donde es trivial.
    """
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
    """Avisadas hace más de los días de gracia y que no volvieron.

    Se vuelve a comprobar la actividad, no solo la fecha del aviso: si la
    persona entró después de recibirlo, la cuenta sale de la lista y su marca
    se limpia en el mismo paso.
    """
    ahora = ahora or timezone.now()
    corte = ahora - relativedelta(days=DIAS_GRACIA)

    candidatas = (_cuentas(usuario)
                  .filter(profile__aviso_inactividad_enviado__lt=corte))

    salida = []
    for cuenta in candidatas:
        perfil = _perfil(cuenta)
        if ultima_senal(cuenta, perfil) > perfil.aviso_inactividad_enviado:
            # Volvió después del aviso: se cancela el proceso.
            perfil.aviso_inactividad_enviado = None
            perfil.save(update_fields=['aviso_inactividad_enviado'])
            continue
        salida.append((cuenta, perfil))
    return salida


def destinatario(usuario, perfil=None):
    """El User manda: es el correo con el que se recupera la contraseña."""
    if usuario.email:
        return usuario.email
    perfil = perfil if perfil is not None else _perfil(usuario)
    return perfil.email or ''


def avisar(usuario, perfil=None, ahora=None):
    """Manda el aviso y anota la fecha. Devuelve True si el correo salió."""
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
    """Borra la cuenta y todo lo que cuelga de ella.

    La cascada se lleva movimientos, cuotas, personas, préstamos, metas,
    suscripciones, categorías, presupuesto, sesiones y segundo factor. La
    foto no viaja en la cascada: vive en R2 o en el disco, y la borra la
    señal post_delete del perfil.
    """
    uid, nombre = usuario.pk, usuario.get_username()
    dias = dias_inactivo(usuario, perfil)
    usuario.delete()
    log.warning('Cuenta borrada por inactividad: id=%s usuario=%s dias=%s',
                uid, nombre, dias)
