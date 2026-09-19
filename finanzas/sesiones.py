"""Sesiones abiertas: registro, listado y cierre remoto.

Por qué hace falta. Hasta ahora, quien entraba en un computador prestado y
se olvidaba de salir no tenía ninguna forma de cerrar esa sesión: cambiar la
contraseña tampoco la cierra (Django mantiene la sesión activa con
update_session_auth_hash, y el atacante ya está dentro). La única salida era
esperar ocho horas a que caducara.

Cómo funciona. Al entrar se anota una fila en SesionActiva con la clave de
sesión, la IP y el agente del navegador. Cerrar una sesión borra su fila de
django_session, y la próxima petición de ese navegador llega sin sesión
válida: queda fuera en el acto, sin esperar nada.

Depende del backend de sesiones en base (el de Django por defecto). Con un
backend solo en caché, Session.objects no ve nada y el cierre remoto no
tendría efecto — de ahí que settings no cambie SESSION_ENGINE.
"""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.dispatch import receiver
from django.utils import timezone

from .models import SesionActiva
from .seguridad import _ip

log = logging.getLogger('finanzas')

MINUTOS_REFRESCO = 15
CLAVE_VISTA = 'sesion_vista'


def _agente(request):
    return (request.META.get('HTTP_USER_AGENT') or '')[:300]


def _ip_valida(request):
    """La IP del cliente, o None si no es una dirección válida.

    La cabecera X-Forwarded-For la escribe el proxy y puede venir con
    cualquier cosa. Un valor así revienta al guardarlo en el campo de IP, y
    anotar la sesión no debe poder fallar por un dato decorativo.
    """
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_ipv46_address

    bruta = _ip(request) or ''
    try:
        validate_ipv46_address(bruta)
    except ValidationError:
        return None
    return bruta


def registrar(request, usuario):
    """Anota la sesión recién abierta, o actualiza la que se reusa.

    La clave puede no existir todavía si la sesión está vacía; save() la
    crea. Sin eso no habría nada que anotar ni que cerrar después.
    """
    if not request.session.session_key:
        request.session.save()

    clave = request.session.session_key
    if not clave:
        return None

    fila, _ = SesionActiva.objects.update_or_create(
        clave=clave,
        defaults={
            'usuario': usuario,
            'ip': _ip_valida(request),
            'agente': _agente(request),
            'ultima_vez': timezone.now(),
        },
    )
    request.session[CLAVE_VISTA] = timezone.now().isoformat()
    return fila


def tocar(request):
    """Refresca «visto por última vez», como mucho cada cuarto de hora.

    Una escritura por petición sería un UPDATE por pantalla cargada. La marca
    del último refresco vive en la sesión, que ya está en memoria, así que el
    coste real son cuatro escrituras por hora de uso.
    """
    clave = request.session.session_key
    if not clave:
        return

    ahora = timezone.now()
    marca = request.session.get(CLAVE_VISTA)
    if marca:
        try:
            from datetime import datetime
            visto = datetime.fromisoformat(marca)
            if (ahora - visto).total_seconds() < MINUTOS_REFRESCO * 60:
                return
        except (TypeError, ValueError):
            pass

    actualizadas = SesionActiva.objects.filter(clave=clave).update(ultima_vez=ahora)
    if not actualizadas:
        # Sesión abierta antes de que existiera esta tabla, o fila borrada a
        # mano. Se crea ahora para que no quede invisible en la pantalla.
        usuario = getattr(request, 'user', None)
        if usuario and usuario.is_authenticated:
            SesionActiva.objects.create(
                usuario=usuario, clave=clave, ip=_ip_valida(request),
                agente=_agente(request), ultima_vez=ahora)
    request.session[CLAVE_VISTA] = ahora.isoformat()


def limpiar(usuario):
    """Borra las filas cuya sesión ya no existe (caducó o se cerró sola)."""
    claves = set(SesionActiva.objects.filter(usuario=usuario)
                 .values_list('clave', flat=True))
    if not claves:
        return
    vivas = set(Session.objects.filter(session_key__in=claves)
                .values_list('session_key', flat=True))
    muertas = claves - vivas
    if muertas:
        SesionActiva.objects.filter(clave__in=muertas).delete()


def listar(usuario, clave_actual=''):
    """Las sesiones abiertas, la de ahora primero y marcada."""
    limpiar(usuario)
    filas = list(SesionActiva.objects.filter(usuario=usuario))
    for f in filas:
        f.es_actual = (f.clave == clave_actual)
    filas.sort(key=lambda f: (not f.es_actual, -f.ultima_vez.timestamp()))
    return filas


def cerrar(usuario, clave):
    """Cierra UNA sesión. Devuelve True si existía y era de esta cuenta.

    El filtro por usuario no es decorativo: sin él, una clave ajena enviada
    en el formulario cerraría la sesión de otra persona.
    """
    fila = SesionActiva.objects.filter(usuario=usuario, clave=clave).first()
    if not fila:
        return False
    Session.objects.filter(session_key=clave).delete()
    fila.delete()
    log.info('Sesión cerrada a distancia: usuario=%s', usuario.pk)
    return True


def cerrar_otras(usuario, clave_actual):
    """Cierra todo menos la sesión desde la que se pide. Devuelve cuántas."""
    otras = list(SesionActiva.objects.filter(usuario=usuario)
                 .exclude(clave=clave_actual).values_list('clave', flat=True))
    if not otras:
        return 0
    Session.objects.filter(session_key__in=otras).delete()
    SesionActiva.objects.filter(clave__in=otras).delete()
    log.warning('Cerradas %s sesiones a distancia: usuario=%s', len(otras), usuario.pk)
    return len(otras)


@receiver(user_logged_in)
def _al_entrar(sender, request, user, **kwargs):
    try:
        registrar(request, user)
    except Exception:
        # Anotar la sesión no puede impedir entrar.
        log.exception('No se pudo registrar la sesión de %s', getattr(user, 'pk', '?'))


@receiver(user_logged_out)
def _al_salir(sender, request, user, **kwargs):
    if not (request and user):
        return
    clave = getattr(request.session, 'session_key', None)
    if clave:
        SesionActiva.objects.filter(clave=clave).delete()
