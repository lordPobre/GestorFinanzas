from django.core.exceptions import ObjectDoesNotExist

from ..templatetags.moneda import money
from .mes import MESES_LARGOS

UMBRAL_AMARILLO = 80

NOMBRES_MONEDA = {
    'CLP': 'pesos', 'ARS': 'pesos', 'MXN': 'pesos', 'COP': 'pesos',
    'USD': 'dólares', 'EUR': 'euros', 'PEN': 'soles', 'BRL': 'reales',
}

ETIQUETAS = {
    'verde': 'Vas bien',
    'amarillo': 'Cerca del límite',
    'rojo': 'Pasaste el límite',
}


def _codigo_moneda(usuario):
    try:
        return usuario.profile.moneda or 'CLP'
    except ObjectDoesNotExist:
        return 'CLP'


def _hablado(monto, usuario):
    entero = f'{round(abs(monto)):,}'.replace(',', '.')
    return f'{entero} {NOMBRES_MONEDA.get(_codigo_moneda(usuario), "pesos")}'


def estado_esfera(usuario, resumen, presupuesto, mes, es_mes_actual, simbolo='$'):
    gastado = float(resumen['gastos']) + float(resumen['total_cuotas_mes'])

    if presupuesto and presupuesto.limite_mensual and float(presupuesto.limite_mensual) > 0:
        base = float(presupuesto.limite_mensual)
        de_que = 'de tu presupuesto'
    elif float(resumen['ingresos']) > 0:
        base = float(resumen['ingresos'])
        de_que = 'de lo que te entró'
    else:
        texto = 'Define tu presupuesto en Perfil o anota tus ingresos para ver cómo vas.'
        return {'estado': 'neutro', 'pct': None, 'etiqueta': 'Sin presupuesto',
                'texto': texto, 'frase': texto}

    pct = round(gastado / base * 100)
    resto = base - gastado
    if pct >= 100:
        estado = 'rojo'
    elif pct >= UMBRAL_AMARILLO:
        estado = 'amarillo'
    else:
        estado = 'verde'

    nombre_mes = MESES_LARGOS[mes - 1].lower()
    queda = money(resto, simbolo)
    pasado = money(-resto, simbolo)
    queda_h = _hablado(resto, usuario)

    if es_mes_actual:
        if estado == 'verde':
            texto = f'Llevas {money(gastado, simbolo)} de {money(base, simbolo)}. Te quedan {queda} para el mes.'
            cola = f'Vas bien: te quedan {queda_h} para el mes.'
        elif estado == 'amarillo':
            texto = f'Usaste el {pct}% {de_que}. Te quedan {queda} hasta fin de mes.'
            cola = f'Estás cerca del límite: te quedan {queda_h} hasta fin de mes.'
        else:
            texto = f'Te pasaste por {pasado}. Revisa qué gastos puedes mover al próximo mes.'
            cola = f'Te pasaste por {queda_h}. Revisa qué gastos puedes mover al próximo mes.'
        frase = f'Este mes llevas el {pct} por ciento {de_que}. {cola}'
    else:
        if estado == 'rojo':
            texto = f'En {nombre_mes} usaste el {pct}% {de_que}. Te pasaste por {pasado}.'
            cola = f'Te pasaste por {queda_h}.'
        else:
            texto = f'En {nombre_mes} usaste el {pct}% {de_que}. Te sobraron {queda}.'
            cola = f'Te sobraron {queda_h}.'
        frase = f'En {nombre_mes} usaste el {pct} por ciento {de_que}. {cola}'

    return {'estado': estado, 'pct': pct, 'etiqueta': ETIQUETAS[estado],
            'texto': texto, 'frase': frase}
