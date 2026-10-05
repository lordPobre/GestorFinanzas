ORDEN_ESTADOS = {'verde': 0, 'amarillo': 1, 'rojo': 2}

AHORA = {
    'verde': 'tus finanzas están sanas',
    'amarillo': 'estás cerca del límite',
    'rojo': 'te pasaste del límite',
}

SIGUE = {
    'verde': 'Tus finanzas siguen sanas.',
    'amarillo': 'Sigues cerca del límite.',
    'rojo': 'Sigues pasado del límite.',
}


def bienvenida_esfera(estado, anterior):
    if estado == 'neutro':
        return {'texto': 'Todavía no hay datos para saber cómo vas este mes.', 'cambio': 'igual'}
    if anterior not in ORDEN_ESTADOS:
        return {'texto': AHORA[estado][0].upper() + AHORA[estado][1:] + '.', 'cambio': 'igual'}
    if anterior == estado:
        return {'texto': SIGUE[estado], 'cambio': 'igual'}
    if ORDEN_ESTADOS[estado] < ORDEN_ESTADOS[anterior]:
        return {'texto': f'Buenas noticias: tus finanzas mejoraron. Ahora {AHORA[estado]}.',
                'cambio': 'mejor'}
    return {'texto': f'Ojo, tus finanzas cambiaron de estado: ahora {AHORA[estado]}.',
            'cambio': 'peor'}
