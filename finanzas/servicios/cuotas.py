from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from ..models import Deuda, Transaccion
from .mes import NOMBRES_MESES


def serie_cuotas(usuario, atras=6, adelante=6):
    hoy = date.today()
    deudas = list(Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'))

    pagos_por_deuda = {d.pk: {p.periodo: p for p in d.pagos.all()} for d in deudas}

    filas = []
    for i in range(-atras, adelante + 1):
        f = date(hoy.year, hoy.month, 1) + relativedelta(months=i)
        periodo = f.year * 100 + f.month

        total = Decimal('0')
        pagado = Decimal('0')
        for d in deudas:
            if periodo not in d.periodos_programados:
                continue
            pago = pagos_por_deuda[d.pk].get(periodo)
            cuota = pago.monto if pago else d.monto_cuota_de(periodo)
            total += cuota
            if pago:
                pagado += cuota

        restante = Decimal('0')
        for d in deudas:
            for p in d.periodos_pendientes:
                if p > periodo:
                    restante += d.monto_cuota_de(p)

        filas.append({
            'periodo': periodo,
            'mes': f'{NOMBRES_MESES[f.month - 1]} {f.year}',
            'mes_corto': NOMBRES_MESES[f.month - 1],
            'total': float(total),
            'pagado': float(pagado),
            'pendiente': float(total - pagado),
            'restante': float(restante),
            'es_pasado': (f.year, f.month) < (hoy.year, hoy.month),
            'es_mes_actual': (f.year, f.month) == (hoy.year, hoy.month),
        })
    return filas

def mis_cuotas_detalle(usuario, hoy):
    mis_cuotas = []
    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if d.esta_saldada:
            continue
        atrasadas = len(d.periodos_atrasados)
        mis_cuotas.append({
            'obj': d,
            'acreedor': d.acreedor,
            'categoria': d.get_categoria_display(),
            'icono': Transaccion(categoria=d.categoria, tipo='EGRESO').icono,
            'color': Transaccion.COLORES_CATEGORIA.get(
                d.categoria, Transaccion.COLORES_CATEGORIA['Otros']),
            'monto_total': round(float(d.monto_total)),
            'pagado': round(float(d.monto_pagado)),
            'restante': round(float(d.monto_restante)),
            'cuota': round(float(d.monto_cuota)),
            'porcentaje': d.porcentaje,
            'cuotas_pagadas': d.cuotas_pagadas,
            'cuotas_totales': d.cuotas_totales,
            'restantes': d.cuotas_restantes,
            'periodo_a_pagar': d.periodo_a_pagar,
            'pagada_este_mes': d.esta_pagada_en(hoy.year * 100 + hoy.month),
            'atrasadas': atrasadas,
            'urgencia': d.urgencia,
            'texto_urgencia': d.texto_urgencia,
            'fin': d.fecha_fin_estimada,
        })
    mis_cuotas.sort(key=lambda x: (-x['atrasadas'], -x['restante']))
    deuda_pagada_total = sum(c['pagado'] for c in mis_cuotas)
    deuda_bruta_total = sum(c['monto_total'] for c in mis_cuotas)
    return mis_cuotas, deuda_pagada_total, deuda_bruta_total

def proyecciones_deuda_activas(todas_las_deudas):
    proyecciones = []
    for d in todas_las_deudas:
        if d.esta_saldada:
            continue
        fin = d.fecha_fin_estimada
        proyecciones.append({
            'acreedor': d.acreedor,
            'fecha_fin': fin,
            'cuotas_restantes': d.cuotas_restantes,
            'monto_cuota': float(d.monto_cuota),
            'mes_fin': f'{NOMBRES_MESES[fin.month - 1]} {fin.year}',
        })
    proyecciones.sort(key=lambda x: x['fecha_fin'])
    return proyecciones
