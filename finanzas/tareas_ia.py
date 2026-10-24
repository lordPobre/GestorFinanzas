import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import signing
from django.utils import timezone

from . import cola

log = logging.getLogger('finanzas')

SAL = 'finanzas.tarea_ia'
GRUPO = 'ia'
MAX_EDAD = 600
SIN_IA = {'ok': False, 'msg': 'IA no disponible'}


def _con_ia(usuario_id):
    return User.objects.filter(pk=usuario_id, is_active=True, profile__analisis_ia=True).exists()


def interpretar(usuario_id, moneda):
    from .analisis import analizar_finanzas
    from .ia import interpretar_con_ia

    if not _con_ia(usuario_id):
        return SIN_IA
    datos = interpretar_con_ia(analizar_finanzas(User.objects.get(pk=usuario_id)), moneda)
    return {'ok': True, 'ia': datos} if datos else SIN_IA


def explicar(usuario_id, resumen, nombres, moneda):
    from .ia_plan import explicar_plan

    if not _con_ia(usuario_id):
        return SIN_IA
    parrafos = explicar_plan(resumen, nombres, moneda)
    return {'ok': True, 'parrafos': parrafos} if parrafos else SIN_IA


def preguntar(usuario_id, conversacion, pregunta, moneda):
    from .ia_preguntas import MAX_TURNOS, cargar, guardar, responder

    if not _con_ia(usuario_id):
        return SIN_IA
    estado = cargar(usuario_id, conversacion)
    if len(estado['turnos']) >= MAX_TURNOS:
        return {'ok': False, 'motivo': 'conversacion'}
    texto = responder(User.objects.get(pk=usuario_id), estado, pregunta, moneda)
    if not texto:
        return SIN_IA
    guardar(usuario_id, conversacion, estado)
    turno = len(estado['turnos'])
    return {'ok': True, 'texto': texto, 'pregunta': pregunta, 'turno': turno,
            'quedan': MAX_TURNOS - turno}


def purgar():
    from django_q.models import Task

    limite = timezone.now() - timedelta(seconds=MAX_EDAD)
    return Task.objects.filter(group=GRUPO, stopped__lt=limite).delete()[0]


def lanzar(usuario, funcion, *args):
    ruta = f'{funcion.__module__}.{funcion.__name__}'
    opciones = {'group': GRUPO}
    if cola.sincronica():
        hecho = cola.recoger(cola.encolar(ruta, *args, q_options=opciones))
        return hecho.get('resultado') or SIN_IA
    try:
        tarea = cola.encolar(ruta, *args, q_options=opciones)
    except Exception:
        log.exception('No se pudo dejar la tarea de IA en la cola; corre al tiro')
        return funcion(*args)
    purgar()
    return {'ok': True, 'tarea': signing.dumps({'t': tarea, 'u': usuario.pk}, salt=SAL)}


def estado(usuario, firmado):
    try:
        datos = signing.loads(firmado or '', salt=SAL, max_age=MAX_EDAD)
    except signing.BadSignature:
        return None
    if not isinstance(datos, dict) or datos.get('u') != usuario.pk:
        return None
    hecho = cola.recoger(datos.get('t'))
    if not hecho['listo']:
        return {'listo': False}
    final = hecho.get('resultado') if hecho.get('ok') else None
    return {'listo': True, **(final if isinstance(final, dict) else SIN_IA)}
