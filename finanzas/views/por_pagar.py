from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..dinero import suma
from ..servicios.mes import nombre_mes_es
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


def _filtro_de(tipo):
    return next((clave for clave, _, tipos in FILTROS if tipo in tipos), 'cuenta')


@login_required(login_url='/login/')
def por_pagar(request):
    hoy = date.today()
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
    return render(request, 'finanzas/por_pagar.html', contexto)
