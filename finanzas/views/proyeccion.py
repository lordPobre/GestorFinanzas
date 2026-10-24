from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.dateformat import format as formato_fecha
from django.views.decorators.http import require_GET

from ..dinero import a_decimal, redondear
from ..templatetags.moneda import money
from .comun import simbolo_de

MAX_COBROS = 8


def _entero(valor):
    return int(redondear(a_decimal(valor)))


def _corto(fecha):
    return formato_fecha(fecha, 'j b')


@login_required(login_url='/login/')
@require_GET
def proyeccion_inicio(request):
    from ..servicios.proyeccion import proyeccion

    simbolo = simbolo_de(request.user)
    p = proyeccion(request.user)
    if not p['dias'] or p['base']['meses_base'] < 1:
        return JsonResponse({'ok': False})

    primero = p['dias'][0]
    inicio = a_decimal(primero['saldo']) + sum((a_decimal(c['monto']) for c in primero['cobros']), a_decimal(0))
    fin = a_decimal(p['dias'][-1]['saldo'])
    cobros = [{'dia': _corto(c['fecha']), 'nombre': c['nombre'], 'monto': money(c['monto'], simbolo)}
              for d in p['dias'] for c in d['cobros']]

    meses = []
    for m in p['meses']:
        if m['actual']:
            continue
        libre = a_decimal(m['libre'])
        ingreso = a_decimal(m['ingreso'])
        pct = 0 if ingreso <= 0 else max(0, min(100, _entero(libre / ingreso * 100)))
        nombre = m['etiqueta'].split()[0]
        meses.append({'nombre': nombre.capitalize(), 'corto': nombre[:3].capitalize(),
                      'libre': money(libre, simbolo), 'negativo': libre < 0,
                      'justo': m['periodo'] == p['mas_justo'], 'pct': pct})

    return JsonResponse({
        'ok': True,
        'inicio': _entero(inicio),
        'dias': [{'s': _entero(d['saldo']), 'cobro': bool(d['cobros'])} for d in p['dias']],
        'ultimo': _corto(p['dias'][-1]['fecha']),
        'fin': money(fin, simbolo),
        'fin_negativo': fin < 0,
        'cobros': cobros[:MAX_COBROS],
        'mas_cobros': max(0, len(cobros) - MAX_COBROS),
        'meses': meses,
        'pocos_datos': p['base']['meses_base'] < 2,
    })
