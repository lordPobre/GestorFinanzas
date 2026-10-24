import calendar
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from .. import fechas
from ..dinero import a_decimal, suma
from ..models import Deuda, Prestamo, Suscripcion
from ..plan import mes_tipico
from .mes import nombre_mes_es, resumen_mes
from .pendientes import pendientes_del_mes

MESES_ADELANTE = 3
MAX_MESES = 12
CERO = Decimal('0')


def _periodo(fecha):
    return fecha.year * 100 + fecha.month


def _cobro(fecha, nombre, monto, tipo):
    return {'fecha': fecha, 'nombre': nombre, 'monto': a_decimal(monto), 'tipo': tipo}


def _cuotas_compra(compra, hoy):
    monto = a_decimal(compra.get('monto'))
    n = max(1, min(MAX_MESES, int(compra.get('cuotas') or 1)))
    if monto <= 0:
        return {}
    nombre = compra.get('nombre') or 'Compra nueva'
    cuota = (monto / n).quantize(Decimal('1'))
    desde = 0 if n == 1 else 1
    salida = {}
    for i in range(n):
        f = date(hoy.year, hoy.month, 1) + relativedelta(months=desde + i)
        valor = monto - cuota * (n - 1) if i == n - 1 else cuota
        fecha = hoy if desde + i == 0 else f
        salida[_periodo(f)] = _cobro(fecha, nombre, valor, 'compra')
    return salida


def _dias_del_mes(usuario, hoy, disponible, deudas, extra):
    _, ultimo = calendar.monthrange(hoy.year, hoy.month)
    cobros = {}
    for i in pendientes_del_mes(usuario, hoy.year, hoy.month, deudas):
        if i['pagado']:
            continue
        fecha = max(i['fecha'], hoy)
        cobros.setdefault(fecha, []).append(_cobro(fecha, i['nombre'], i['monto'], i['tipo']))
    saldo = disponible + suma(c['monto'] for lista in cobros.values() for c in lista)
    if extra:
        cobros.setdefault(hoy, []).append(extra)
    dias = []
    for n in range(hoy.day, ultimo + 1):
        f = date(hoy.year, hoy.month, n)
        del_dia = cobros.get(f, [])
        saldo -= suma(c['monto'] for c in del_dia)
        dias.append({'fecha': f, 'saldo': saldo, 'cobros': del_dia})
    return dias


def _cuotas_del_mes(deudas, periodo):
    return [_cobro(d.fecha_cobro_de(periodo), d.acreedor, d.monto_cuota_de(periodo), 'cuota')
            for d in deudas
            if periodo in d.periodos_programados and not d.esta_pagada_en(periodo)]


def _suscripciones_del_mes(suscripciones, year, month):
    _, ultimo = calendar.monthrange(year, month)
    inicio, fin = date(year, month, 1), date(year, month, ultimo)
    return [_cobro(s.fecha_cobro_de(year * 100 + month), s.nombre, s.monto, 'servicio')
            for s in suscripciones
            if s.fecha_inicio <= fin and (s.fecha_cancelada is None or s.fecha_cancelada >= inicio)]


def _prestamos_futuros(prestamos, hoy, meses):
    salida = {}
    for pr in prestamos:
        if pr.tipo != 'CUOTAS' or pr.esta_pagado:
            continue
        resta = pr.monto_pendiente - pr.falta_este_mes(hoy.year, hoy.month)
        for f in meses:
            if resta <= 0:
                break
            pago = min(pr.monto_cuota, resta)
            resta -= pago
            salida.setdefault(_periodo(f), []).append(
                _cobro(pr.dia_de_pago(f.year, f.month), pr.persona.nombre, pago, 'debo'))
    return salida


def proyeccion(usuario, meses=MESES_ADELANTE, compra=None, hoy=None):
    hoy = hoy or fechas.hoy()
    meses = max(1, min(MAX_MESES, int(meses)))
    cobros_compra = _cuotas_compra(compra, hoy) if compra else {}
    if cobros_compra:
        ultimo = max(cobros_compra)
        faltan = (ultimo // 100 - hoy.year) * 12 + ultimo % 100 - hoy.month
        meses = max(meses, min(MAX_MESES, faltan))

    r = resumen_mes(usuario, hoy.year, hoy.month)
    tipico = mes_tipico(usuario, hoy)
    deudas = list(Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'))
    suscripciones = list(Suscripcion.objects.filter(usuario=usuario, activa=True))
    prestamos = list(Prestamo.objects.filter(persona__usuario=usuario, persona__lado='LE_DEBO')
                     .select_related('persona').prefetch_related('abonos'))

    ingreso = a_decimal(tipico['ingreso'])
    variable = max(CERO, a_decimal(tipico['gasto']) - suma(s.monto for s in suscripciones))
    primero = date(hoy.year, hoy.month, 1)
    futuros = [primero + relativedelta(months=i) for i in range(1, meses + 1)]
    debo = _prestamos_futuros(prestamos, hoy, futuros)

    compra_hoy = cobros_compra.get(_periodo(hoy))
    dias = _dias_del_mes(usuario, hoy, r['disponible'], deudas, compra_hoy)
    lista = [{
        'periodo': _periodo(hoy),
        'etiqueta': nombre_mes_es(hoy.year, hoy.month, capitalizado=False),
        'actual': True,
        'ingreso': r['ingresos'],
        'cobros': [c for d in dias for c in d['cobros']],
        'libre': r['disponible'] - (compra_hoy['monto'] if compra_hoy else CERO),
    }]
    for f in futuros:
        p = _periodo(f)
        cobros = (_cuotas_del_mes(deudas, p) + _suscripciones_del_mes(suscripciones, f.year, f.month)
                  + debo.get(p, []))
        if p in cobros_compra:
            cobros.append(cobros_compra[p])
        cobros.sort(key=lambda c: c['fecha'])
        lista.append({
            'periodo': p,
            'etiqueta': nombre_mes_es(f.year, f.month, capitalizado=False),
            'actual': False,
            'ingreso': ingreso,
            'gasto_variable': variable,
            'cobros': cobros,
            'libre': ingreso - variable - suma(c['monto'] for c in cobros),
        })

    justo = min(lista, key=lambda m: m['libre'])
    return {
        'meses': lista,
        'mas_justo': justo['periodo'],
        'dias': dias,
        'dia_mas_justo': min(dias, key=lambda d: d['saldo'])['fecha'] if dias else None,
        'alcanza': all(m['libre'] >= 0 for m in lista),
        'base': {'ingreso': ingreso, 'gasto_variable': variable, 'meses_base': tipico['meses_base']},
    }
