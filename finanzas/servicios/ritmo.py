import calendar
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Q, Sum

from ..models import Categoria, Transaccion
from .panel import TONOS_INSIGHT

DIA_MINIMO = 7
MESES_HISTORIAL = 3
MINIMO_MESES = 2
SUBE = 1.2
BAJA = 0.85
DIFERENCIA_MINIMA = 10000
MAXIMO = 3


def _plata(valor, simbolo):
    return f'{simbolo}{round(valor):,}'.replace(',', '.')


def _dia_a_dia(usuario, desde, hasta):
    filas = (Transaccion.objects
             .filter(usuario=usuario, tipo='EGRESO', es_cuota=False, suscripcion__isnull=True,
                     fecha__gte=desde, fecha__lte=hasta)
             .exclude(Q(descripcion__startswith='Pendiente: ') | Q(descripcion__startswith='Suscripción: '))
             .values('categoria').annotate(total=Sum('monto')))
    salida = defaultdict(float)
    for f in filas:
        salida[f['categoria'] or 'Otros'] += float(f['total'])
    return salida


def _aviso(tipo, icono, texto):
    tono = TONOS_INSIGHT[tipo]
    return {'tipo': tipo, 'icono': icono, 'texto': texto, **tono, 'etiqueta': 'A este ritmo'}


def ritmo_del_mes(usuario, hoy=None, simbolo='$'):
    hoy = hoy or date.today()
    if hoy.day < DIA_MINIMO:
        return []

    inicio = date(hoy.year, hoy.month, 1)
    ultimo = calendar.monthrange(hoy.year, hoy.month)[1]
    actual = _dia_a_dia(usuario, inicio, hoy)
    if not actual:
        return []

    total_mes, resto_mes = defaultdict(float), defaultdict(float)
    meses = 0
    for i in range(1, MESES_HISTORIAL + 1):
        m = inicio - relativedelta(months=i)
        fin = date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])
        completo = _dia_a_dia(usuario, m, fin)
        if not completo:
            continue
        meses += 1
        corte = date(m.year, m.month, min(hoy.day, fin.day))
        hasta_corte = _dia_a_dia(usuario, m, corte)
        for cat, valor in completo.items():
            total_mes[cat] += valor
            resto_mes[cat] += valor - hasta_corte.get(cat, 0)

    if meses < MINIMO_MESES:
        return []

    mapa = Categoria.mapa(usuario)
    dias_restantes = max(1, ultimo - hoy.day)
    alertas = []
    for cat, llevas in actual.items():
        promedio = total_mes.get(cat, 0) / meses
        if promedio <= 0:
            continue
        proyeccion = llevas + resto_mes.get(cat, 0) / meses
        if proyeccion < promedio * SUBE or proyeccion - promedio < DIFERENCIA_MINIMA:
            continue
        datos = mapa.get(cat, {})
        nombre = datos.get('label', cat)
        pct = round((proyeccion / promedio - 1) * 100)
        margen = promedio - llevas
        if margen > 0:
            consejo = (f'Para quedar en tu promedio te quedan {_plata(margen, simbolo)}, '
                       f'unos {_plata(margen / dias_restantes, simbolo)} por día.')
        else:
            consejo = f'Ya pasaste tu promedio de {_plata(promedio, simbolo)} para todo el mes.'
        alertas.append((proyeccion - promedio, _aviso(
            'alerta', datos.get('icono') or 'fa-gauge-high',
            f'Terminas el mes con {_plata(proyeccion, simbolo)} en {nombre}, '
            f'{pct}% más que tu promedio. {consejo}',
        )))

    if alertas:
        alertas.sort(key=lambda a: -a[0])
        return [a for _, a in alertas[:MAXIMO]]

    promedio_total = sum(total_mes.values()) / meses
    proyeccion_total = sum(actual.values()) + sum(resto_mes.values()) / meses
    if promedio_total > 0 and proyeccion_total <= promedio_total * BAJA:
        pct = round((1 - proyeccion_total / promedio_total) * 100)
        return [_aviso('exito', 'fa-gauge',
                       f'Terminas el mes gastando {pct}% menos que tu promedio en el día a día.')]
    return []
