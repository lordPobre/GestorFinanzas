import math
import re
from datetime import date

from .analisis import analizar_finanzas
from .models import Deuda, MetaAhorro, Suscripcion

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


def armar_plan(usuario):
    a = analizar_finanzas(usuario)
    hoy = date.today()

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
    meta = round((a['gasto_mensual'] + a['cuota_mensual_total']) * 3)

    sobra = max(0, a['flujo_libre'])
    ahorro = _redondear(sobra * 0.4)
    extra = _redondear(sobra * 0.3) if deudas else 0

    return {
        'tiene_datos': a['tiene_datos'],
        'sobra': sobra,
        'falta': max(0, -a['flujo_libre']),
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
