from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .. import diseno, fechas
from ..dinero import suma
from ..servicios.mes import nombre_mes_es, resumen_mes
from ..servicios.mes_elegido import mes_pedido, selector_mes
from ..servicios.pendientes import pendientes_del_mes
from .comun import contadores

FILTROS = (
    ('cuota', 'Cuotas', ('cuota',)),
    ('servicio', 'Servicios', ('servicio',)),
    ('cuenta', 'Cuentas', ('cuenta', 'gasto')),
    ('debo', 'Personas', ('debo',)),
)
ICONOS = {'cuota': 'fa-credit-card', 'servicio': 'fa-rotate', 'cuenta': 'fa-file-invoice',
          'gasto': 'fa-receipt', 'debo': 'fa-hand-holding-dollar'}
DESGLOSE_2C = (
    ('cuota', 'Cuotas de este mes'),
    ('servicio', 'Suscripciones'),
    ('cuenta', 'Cuentas y gastos'),
    ('debo', 'A personas'),
)


def _filtro_de(tipo):
    return next((clave for clave, _, tipos in FILTROS if tipo in tipos), 'cuenta')


def _arrastradas(usuario, hoy):
    r = resumen_mes(usuario, hoy.year, hoy.month)
    salida = []
    for c in r['cuotas_arrastradas']:
        d = c['deuda']
        salida.append({
            'nombre': d.acreedor,
            'detalle': f'Cuota {d.periodos_programados.index(c["periodo"]) + 1} de {d.cuotas_totales}',
            'etiqueta': c['etiqueta'].lower(),
            'monto': c['monto'],
            'periodo': c['periodo'],
            'deuda_id': d.pk,
        })
    return salida, r['atrasado_arrastrado']


@login_required(login_url='/login/')
def por_pagar(request):
    hoy = fechas.hoy()
    year, month = mes_pedido(request, hoy)
    es_actual = (year, month) == (hoy.year, hoy.month)
    items = pendientes_del_mes(request.user, year, month)
    fin_semana = hoy + timedelta(days=7)

    grupos = {'atrasado': [], 'semana': [], 'despues': [], 'pagado': []}
    for i in items:
        i['filtro'] = _filtro_de(i['tipo'])
        i['icono_lista'] = ICONOS.get(i['tipo'], 'fa-circle')
        if i['pagado']:
            grupos['pagado'].append(i)
        elif i['atrasado']:
            grupos['atrasado'].append(i)
        elif es_actual and i['fecha'] <= fin_semana:
            grupos['semana'].append(i)
        else:
            grupos['despues'].append(i)

    pendientes = [i for i in items if not i['pagado']]
    total = suma(i['monto'] for i in items)
    pagado = suma(i['monto'] for i in items if i['pagado'])
    secciones = [
        ('atrasado', 'Atrasado', grupos['atrasado']),
        ('semana', 'Esta semana', grupos['semana']),
        ('despues', 'Más adelante' if es_actual else 'Por pagar', grupos['despues']),
        ('pagado', 'Ya pagado', grupos['pagado']),
    ]
    contexto = {
        'secciones': [s for s in secciones if s[2]],
        'falta': total - pagado,
        'pagado': pagado,
        'total': total,
        'n_pendientes': len(pendientes),
        'filtros': [{'clave': c, 'nombre': n, 'cuantos': sum(1 for i in pendientes if i['filtro'] == c)}
                    for c, n, _ in FILTROS],
        'nombre_mes': nombre_mes_es(year, month),
        'mes_sel': selector_mes(request.user, year, month, hoy),
    }
    contexto.update(contadores(request.user))

    if not diseno.activo(request):
        return render(request, 'finanzas/por_pagar.html', contexto)

    arrastradas, arrastrado = _arrastradas(request.user, hoy) if es_actual else ([], 0)
    for f in contexto['filtros']:
        if f['clave'] == 'cuota':
            f['cuantos'] += len(arrastradas)
    contexto.update({
        'n_todo': len(pendientes) + len(arrastradas),
        'items': items,
        'n_pagados': len(items) - len(pendientes),
        'arrastradas': arrastradas,
        'arrastrado': arrastrado,
        'desglose': [{'nombre': n, 'monto': suma(i['monto'] for i in pendientes if i['filtro'] == c)}
                     for c, n in DESGLOSE_2C if any(i['filtro'] == c for i in pendientes)],
    })
    return render(request, 'finanzas/por_pagar_2c.html', contexto)
