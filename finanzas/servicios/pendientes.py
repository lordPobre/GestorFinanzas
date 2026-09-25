import calendar
from datetime import date

from django.urls import reverse

from ..models import Deuda, GastoPendiente, Suscripcion, Transaccion


def pendientes_del_mes(usuario, year, month):
    periodo = year * 100 + month
    items = []

    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if periodo not in d.periodos_programados:
            continue
        pago = next((p for p in d.pagos.all() if p.periodo == periodo), None)
        fecha = d.fecha_cobro_de(periodo)
        items.append({
            'tipo': 'cuota',
            'nombre': d.acreedor,
            'detalle': f'Cuota {d.periodos_programados.index(periodo) + 1} de {d.cuotas_totales}',
            'monto': pago.monto if pago else d.monto_cuota_de(periodo),
            'fecha': fecha,
            'pagado': bool(pago),
            'fecha_pago': pago.fecha_pago if pago else None,
            'icono': 'fa-credit-card',
            'url_pagar': reverse('pagar_cuota', args=[d.pk]),
            'url_anular': reverse('anular_cuota', args=[d.pk]),
            'periodo': periodo,
        })

    for s in Suscripcion.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if periodo not in s.periodos_programados:
            continue
        pago = next((p for p in s.pagos.all() if p.periodo == periodo), None)
        items.append({
            'tipo': 'servicio',
            'nombre': s.nombre,
            'detalle': f'Suscripción · se cobra el {s.dia_cobro}',
            'monto': s.monto,
            'fecha': s.fecha_cobro_de(periodo),
            'pagado': bool(pago),
            'fecha_pago': pago.fecha_pago if pago else None,
            'icono': 'fa-rotate',
            'marca': s.marca,
            'inicial': s.inicial,
            'url_pagar': reverse('pagar_servicio', args=[s.pk]),
            'url_anular': reverse('anular_pago_servicio', args=[s.pk]),
            'periodo': periodo,
        })

    for t in Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO', es_cuota=False, pagado=False,
            fecha__year=year, fecha__month=month,
    ).exclude(descripcion__startswith='Suscripción: ').exclude(
            descripcion__startswith='Pendiente: '):
        items.append({
            'tipo': 'gasto',
            'nombre': t.descripcion or t.get_categoria_display(),
            'detalle': t.get_categoria_display(),
            'monto': t.monto,
            'fecha': t.fecha,
            'pagado': False,
            'fecha_pago': None,
            'icono': t.icono,
            'url_pagar': reverse('pagar_gasto', args=[t.pk]),
            'url_anular': reverse('anular_pago_gasto', args=[t.pk]),
            'periodo': periodo,
        })

    _, ultimo = calendar.monthrange(year, month)
    for g in GastoPendiente.objects.filter(
            usuario=usuario,
            fecha_vencimiento__gte=date(year, month, 1),
            fecha_vencimiento__lte=date(year, month, ultimo)):
        items.append({
            'tipo': 'cuenta',
            'nombre': g.nombre,
            'detalle': g.categoria or 'Cuenta por pagar',
            'monto': g.monto,
            'fecha': g.fecha_vencimiento,
            'pagado': g.pagado,
            'fecha_pago': g.fecha_pago,
            'icono': 'fa-file-invoice',
            'url_pagar': reverse('pagar_gasto_pendiente', args=[g.pk]),
            'url_anular': reverse('anular_gasto_pendiente', args=[g.pk]),
            'periodo': periodo,
        })

    hoy = date.today()
    for it in items:
        it['atrasado'] = not it['pagado'] and it['fecha'] < hoy
    items.sort(key=lambda x: (x['pagado'], not x['atrasado'], x['fecha']))
    return items

def calendario_del_mes(year, month, hoy, eventos_por_dia):
    calendario_datos = []
    for semana in calendar.monthcalendar(year, month):
        fila = []
        for dia in semana:
            if dia == 0:
                fila.append(None)
            else:
                eventos = eventos_por_dia.get(dia, [])
                fila.append({
                    'numero': dia,
                    'es_hoy': (dia == hoy.day and month == hoy.month and year == hoy.year),
                    'eventos': eventos,
                    'tiene_pagos': bool(eventos),
                    'todo_pagado': bool(eventos) and all(e['estado'] == 'pagado' for e in eventos),
                    'total_dia': sum(float(e['monto']) for e in eventos),
                })
        calendario_datos.append(fila)
    dias_con_pago = [d for semana in calendario_datos for d in semana if d and d['tiene_pagos']]
    return calendario_datos, dias_con_pago
