from .cuotas import serie_cuotas


def mes_a_mes(usuario):
    serie = serie_cuotas(usuario)
    tope = max([f['total'] for f in serie] + [1])
    for f in serie:
        f['alto_pagado'] = round(f['pagado'] / tope * 100)
        f['alto_pendiente'] = round(f['pendiente'] / tope * 100) if f['total'] else 3
        f['corto'] = f['mes_corto'][:3]
        f['titulo'] = f['mes'].capitalize() + (' · este mes' if f['es_mes_actual'] else '')
        f['despues'] = f['mes_corto']
    return serie
