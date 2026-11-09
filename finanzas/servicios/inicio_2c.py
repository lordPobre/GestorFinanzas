from .cuotas import serie_cuotas
from .panel import desglose_categorias


def datos_inicio_2c(usuario, r, plata, proyecciones_deuda):
    cifra = [
        {'etiqueta': 'Entró', 'signo': '+', 'monto': plata(r['ingresos']), 'tono': 'verde'},
        {'etiqueta': 'Gastos', 'signo': '−', 'monto': plata(r['gastos']), 'tono': ''},
        {'etiqueta': 'Cuotas del mes', 'signo': '−', 'monto': plata(r['total_cuotas_mes']), 'tono': ''},
    ]
    if r['atrasado_arrastrado']:
        cifra.append({'etiqueta': 'Cuotas que no pagaste', 'signo': '−',
                      'monto': plata(r['atrasado_arrastrado']), 'tono': 'rojo'})
    if r['total_debo_mes']:
        cifra.append({'etiqueta': 'Le debes a personas', 'signo': '−',
                      'monto': plata(r['total_debo_mes']), 'tono': ''})

    serie = serie_cuotas(usuario, atras=0, adelante=5)
    tope = max([f['total'] for f in serie] + [1])
    for f in serie:
        f['alto_pct'] = max(8, round(f['total'] / tope * 100))
        f['corto'] = f['mes_corto'][:3]

    return {
        'cifra_2c': cifra,
        'disponible_abs': plata(abs(r['disponible'])),
        'categorias_2c': desglose_categorias(usuario, r)[:4],
        'cuotas_6_meses': serie,
        'termina_todo': proyecciones_deuda[-1]['mes_fin'] if proyecciones_deuda else None,
        'ultimo_dia': r['ultimo_dia'],
    }
