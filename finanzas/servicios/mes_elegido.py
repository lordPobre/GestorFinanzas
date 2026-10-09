import re
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Min

from ..models import Transaccion
from .mes import MESES_LARGOS, nombre_mes_es

MAX_MESES = 36


def mes_pedido(request, hoy=None):
    hoy = hoy or date.today()
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', (request.GET.get('mes') or '').strip())
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and year >= 2000 and (year, month) <= (hoy.year, hoy.month):
            return year, month
    return hoy.year, hoy.month


def _opcion(f):
    return {'valor': f'{f.year}-{f.month:02d}', 'nombre': nombre_mes_es(f.year, f.month)}


def selector_mes(usuario, year, month, hoy=None):
    hoy = hoy or date.today()
    este = date(hoy.year, hoy.month, 1)
    elegido = date(year, month, 1)

    primera = Transaccion.objects.filter(usuario=usuario).aggregate(f=Min('fecha'))['f']
    inicio = este - relativedelta(months=MAX_MESES - 1)
    inicio = max(inicio, date(primera.year, primera.month, 1)) if primera else este
    inicio = min(inicio, elegido)

    opciones, f = [], este
    while f >= inicio:
        opciones.append({**_opcion(f), 'elegido': f == elegido})
        f -= relativedelta(months=1)

    anterior = elegido - relativedelta(months=1)
    siguiente = elegido + relativedelta(months=1)
    es_actual = elegido == este
    previo = MESES_LARGOS[anterior.month - 1]

    return {
        'opciones': opciones,
        'nombre': nombre_mes_es(year, month),
        'corto': f'{MESES_LARGOS[month - 1][:3].capitalize()} {year}',
        'es_actual': es_actual,
        'anterior': _opcion(anterior) if anterior >= inicio else None,
        'siguiente': _opcion(siguiente) if siguiente <= este else None,
        'en_mes': 'este mes' if es_actual else f'en {MESES_LARGOS[month - 1]}',
        'ref_anterior': 'el mes pasado' if es_actual else f'en {previo}',
    }
