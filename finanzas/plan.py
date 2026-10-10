import calendar
import math
import re
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.db.models.functions import TruncMonth

from .models import Deuda, MetaAhorro, Suscripcion, Transaccion
from .servicios.mes import resumen_mes

MESES_CERRADOS = 3

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

PALABRAS_FONDO = ('imprevist', 'emergencia', 'colchon', 'colchón')

GRUPOS_SUSCRIPCION = (
    ('de streaming', ('netflix', 'disney', 'prime video', 'amazon prime', 'hbo',
                      'max', 'paramount', 'star+', 'apple tv', 'crunchyroll', 'mubi')),
    ('de música', ('spotify', 'youtube music', 'apple music', 'deezer', 'tidal')),
    ('de almacenamiento', ('icloud', 'google one', 'dropbox', 'onedrive')),
)

ESTRATEGIAS = ('saldo', 'cuota')


def etiqueta_mes(n, anio, mes):
    t = mes - 1 + n - 1
    return f'{MESES[t % 12]} {anio + t // 12}'


def _redondear(valor, paso=5000):
    return int(valor // paso * paso)


def _calza(nombre, palabra):
    return re.search(r'(?<!\w)' + re.escape(palabra) + r'(?!\w)', nombre) is not None


def meses_sin_extra(deuda):
    return math.ceil(deuda['saldo'] / deuda['cuota'])


def ordenar(deudas, estrategia):
    if estrategia == 'cuota':
        return sorted(deudas, key=lambda d: (-d['cuota'], d['saldo']))
    return sorted(deudas, key=lambda d: (d['saldo'], -d['cuota']))


def simular(deudas, extra, estrategia='saldo'):
    filas = [{**d, 'resta': d['saldo'], 'fin': 0} for d in ordenar(deudas, estrategia)]
    if extra <= 0:
        for f in filas:
            f['resta'], f['fin'] = 0, meses_sin_extra(f)
        return filas
    liberado, mes = 0, 0
    while any(f['resta'] > 0 for f in filas) and mes < 600:
        mes += 1
        bolsa = extra + liberado
        for f in filas:
            if f['resta'] <= 0:
                continue
            pago = min(f['cuota'], f['resta'])
            f['resta'] -= pago
            bolsa += f['cuota'] - pago
        for f in filas:
            if bolsa <= 0:
                break
            if f['resta'] <= 0:
                continue
            pago = min(bolsa, f['resta'])
            f['resta'] -= pago
            bolsa -= pago
        liberado = 0
        for f in filas:
            if f['resta'] <= 0:
                f['fin'] = f['fin'] or mes
                liberado += f['cuota']
    return filas


def suscripciones_repetidas(usuario):
    activas = list(Suscripcion.objects.filter(usuario=usuario, activa=True).order_by('nombre'))
    grupos = []
    for etiqueta, palabras in GRUPOS_SUSCRIPCION:
        items = [s for s in activas
                 if any(_calza((s.nombre or '').lower(), p) for p in palabras)]
        if len(items) < 2:
            continue
        mensual = round(sum(float(s.monto) for s in items))
        grupos.append({
            'titulo': f'Tienes {len(items)} {etiqueta}',
            'items': [{'nombre': s.nombre, 'monto': round(float(s.monto))} for s in items],
            'mensual': mensual,
            'anual': mensual * 12,
        })
    return grupos


def _totales_por_mes(usuario, desde, hasta):
    filas = (Transaccion.objects
             .filter(usuario=usuario, fecha__gte=desde, fecha__lte=hasta)
             .exclude(tipo='EGRESO', es_cuota=True)
             .annotate(m=TruncMonth('fecha'))
             .values('m', 'tipo')
             .annotate(t=Sum('monto')))
    totales = {}
    for f in filas:
        clave = (f['m'].year, f['m'].month)
        totales.setdefault(clave, {})[f['tipo']] = float(f['t'] or 0)
    return totales


def promedio_tipico(cerrados, actual, dia, dias_mes):
    ingresos = [m.get('INGRESO', 0) for m in cerrados if m.get('INGRESO', 0) > 0]
    if actual.get('INGRESO', 0) > 0:
        ingresos.append(actual['INGRESO'])
    ingreso = sum(ingresos) / len(ingresos) if ingresos else 0.0

    gastos = [m.get('EGRESO', 0) for m in cerrados if m.get('EGRESO', 0) > 0]
    if gastos:
        gasto = sum(gastos) / len(gastos)
    elif actual.get('EGRESO', 0) > 0:
        gasto = actual['EGRESO'] * dias_mes / max(dia, 1)
    else:
        gasto = 0.0
    return ingreso, gasto, len(gastos)


def mes_tipico(usuario, hoy=None):
    hoy = hoy or date.today()
    inicio = hoy.replace(day=1)
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    totales = _totales_por_mes(usuario, inicio - relativedelta(months=MESES_CERRADOS),
                               date(hoy.year, hoy.month, dias_mes))
    cerrados = []
    for i in range(1, MESES_CERRADOS + 1):
        f = inicio - relativedelta(months=i)
        cerrados.append(totales.get((f.year, f.month), {}))
    actual = totales.get((hoy.year, hoy.month), {})

    ingreso, gasto, meses_base = promedio_tipico(cerrados, actual, hoy.day, dias_mes)
    r = resumen_mes(usuario, hoy.year, hoy.month)
    compromisos = r['total_cuotas_mes'] + r['total_debo_mes']
    return {
        'ingreso': round(ingreso),
        'gasto': round(gasto),
        'compromisos': round(compromisos),
        'flujo': round(ingreso - gasto - compromisos),
        'disponible_mes': max(0, round(r['disponible'])),
        'meses_base': meses_base,
    }


def armar_plan(usuario):
    hoy = date.today()
    t = mes_tipico(usuario, hoy)

    deudas = []
    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if d.esta_saldada:
            continue
        saldo, cuota = round(float(d.monto_restante)), round(float(d.monto_cuota))
        if saldo > 0 and cuota > 0:
            deudas.append({'nombre': (d.acreedor or 'Deuda')[:60], 'saldo': saldo, 'cuota': cuota})

    metas_fondo = [m for m in MetaAhorro.objects.filter(usuario=usuario)
                   if any(p in (m.nombre or '').lower() for p in PALABRAS_FONDO)]
    llevas = round(sum(float(m.monto_actual) for m in metas_fondo))
    meta = round((t['gasto'] + t['compromisos']) * 3)

    sobra = max(0, t['flujo'])
    tope_mes = t['disponible_mes']
    reparte = min(sobra, tope_mes)
    ahorro = _redondear(reparte * 0.4)
    extra = _redondear(reparte * 0.3) if deudas else 0

    return {
        'tiene_datos': t['ingreso'] > 0 or bool(deudas),
        'sobra': sobra,
        'falta': max(0, -t['flujo']),
        'ingreso': t['ingreso'],
        'gasto': t['gasto'],
        'compromisos': t['compromisos'],
        'tope_mes': tope_mes,
        'limitado': 0 < sobra and tope_mes < sobra,
        'meses_base': t['meses_base'],
        'pocos_datos': t['meses_base'] < 2,
        'deudas': deudas,
        'meta': meta,
        'llevas': llevas,
        'tiene_fondo': bool(metas_fondo),
        'suscripciones': suscripciones_repetidas(usuario),
        'datos': {
            'sobra': sobra, 'meta': meta, 'llevas': llevas, 'deudas': deudas,
            'ahorro': ahorro, 'extra': extra, 'anio': hoy.year, 'mes': hoy.month,
        },
    }


def resumen_para_ia(plan, ahorro, extra, estrategia):
    hoy = date.today()
    mes = lambda n: etiqueta_mes(n, hoy.year, hoy.month)
    deudas = plan['deudas']
    filas = simular(deudas, extra, estrategia) if deudas else []

    nombres, lista = {}, []
    for i, f in enumerate(filas, start=1):
        clave = f'D{i}'
        nombres[clave] = f['nombre']
        lista.append({
            'clave': clave, 'saldo': f['saldo'], 'cuota': f['cuota'],
            'termina': mes(f['fin']), 'meses_antes': meses_sin_extra(f) - f['fin'],
        })

    falta_fondo = max(0, plan['meta'] - plan['llevas'])
    meses_fondo = math.ceil(falta_fondo / ahorro) if ahorro and falta_fondo else 0
    resumen = {
        'sobra': plan['sobra'], 'ahorro': ahorro, 'extra': extra,
        'libre': plan['sobra'] - ahorro - extra,
        'estrategia': estrategia,
        'deudas': lista,
        'termina_todo': mes(max(f['fin'] for f in filas)) if filas else '',
        'termina_sin_extra': mes(max(meses_sin_extra(f) for f in filas)) if filas else '',
        'meta_fondo': plan['meta'], 'llevas_fondo': plan['llevas'],
        'porcentaje_fondo': round(plan['llevas'] / plan['meta'] * 100) if plan['meta'] else 0,
        'fondo_completo_en': mes(meses_fondo) if meses_fondo else '',
    }
    return resumen, nombres
