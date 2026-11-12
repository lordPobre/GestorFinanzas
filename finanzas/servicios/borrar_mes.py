import calendar
import secrets
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction

from ..models import Transaccion
from ..rendimiento import limpiar
from .mes import invalidar

MINUTOS = 10
CERO = Decimal('0')
GRUPOS = ('borrar', 'ingresos', 'cuotas', 'suscripciones', 'cuentas')


def _clave(usuario_id, token):
    return f'borrado-mes:{usuario_id}:{token}'


def _grupo(t):
    if t.es_ingreso:
        return 'ingresos'
    if t.es_cuota:
        return 'cuotas'
    if t.es_cobro_suscripcion:
        return 'suscripciones'
    if t.es_cuenta_pendiente:
        return 'cuentas'
    return 'borrar'


def resumen(movimientos):
    salida = {g: {'n': 0, 'total': CERO} for g in GRUPOS}
    for t in movimientos or []:
        fila = salida[_grupo(t)]
        fila['n'] += 1
        fila['total'] += t.monto or CERO
    salida['quedan'] = sum(salida[g]['n'] for g in GRUPOS if g != 'borrar')
    return salida


def _del_mes(usuario, year, month):
    _, ultimo = calendar.monthrange(year, month)
    return (Transaccion.objects
            .filter(usuario=usuario, tipo='EGRESO', es_cuota=False,
                    fecha__gte=date(year, month, 1), fecha__lte=date(year, month, ultimo))
            .exclude(Transaccion.q_vinculados()))


def borrar(usuario, year, month):
    filas = list(_del_mes(usuario, year, month))
    if not filas:
        return None
    campos = [f.attname for f in Transaccion._meta.concrete_fields]
    copia = [{c: getattr(t, c) for c in campos} for t in filas]
    with transaction.atomic():
        Transaccion.objects.filter(pk__in=[t.pk for t in filas]).delete()
    token = secrets.token_urlsafe(12)
    cache.set(_clave(usuario.pk, token), copia, MINUTOS * 60)
    return {'token': token, 'n': len(filas), 'total': sum((t.monto for t in filas), CERO)}


def deshacer(usuario, token):
    if not token:
        return 0
    clave = _clave(usuario.pk, token)
    copia = cache.get(clave)
    if not copia:
        return 0
    cache.delete(clave)
    ids = [c['id'] for c in copia]
    existentes = set(Transaccion.objects.filter(pk__in=ids).values_list('pk', flat=True))
    nuevas = [Transaccion(**c) for c in copia if c['id'] not in existentes and c['usuario_id'] == usuario.pk]
    with transaction.atomic():
        Transaccion.objects.bulk_create(nuevas)
    invalidar(usuario.pk)
    limpiar()
    return len(nuevas)
