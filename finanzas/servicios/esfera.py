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


def _plural(n, uno, varios):
    return uno if n == 1 else varios


def esfera_cuotas(usuario, activas, simbolo='$'):
    if not activas:
        texto = 'No tienes compras en cuotas pendientes.'
        return {'estado': 'verde', 'etiqueta': 'Sin cuotas', 'texto': texto, 'frase': texto}

    restante = sum(float(d.monto_restante) for d in activas)
    del_mes = sum(float(d.monto_cuota) for d in activas)
    atrasadas = sum(len(d.periodos_atrasados) for d in activas)
    monto_atrasado = sum(float(d.monto_atrasado) for d in activas)
    pronto = sum(1 for d in activas if d.urgencia not in ('vencida', 'normal'))
    n = len(activas)
    compras = _plural(n, 'compra', 'compras')

    texto = f'Debes {money(restante, simbolo)} en {n} {compras}. Este mes pagas {money(del_mes, simbolo)}.'
    frase = (f'Debes {_hablado(restante, usuario)} en cuotas, en {n} {compras}. '
             f'Este mes pagas {_hablado(del_mes, usuario)}.')

    if atrasadas:
        estado, etiqueta = 'rojo', _plural(atrasadas, 'Cuota atrasada', 'Cuotas atrasadas')
        cuotas = _plural(atrasadas, 'cuota atrasada', 'cuotas atrasadas')
        texto += f' Tienes {atrasadas} {cuotas}.'
        frase += f' Tienes {atrasadas} {cuotas} por {_hablado(monto_atrasado, usuario)}.'
    elif pronto:
        estado, etiqueta = 'amarillo', 'Vence pronto'
        texto += f' {_plural(pronto, "Una cuota vence", f"{pronto} cuotas vencen")} pronto.'
        frase += f' {_plural(pronto, "Tienes una cuota que vence", f"Tienes {pronto} cuotas que vencen")} pronto.'
    else:
        estado, etiqueta = 'verde', 'Cuotas al día'
        frase += ' Vas al día.'

    return {'estado': estado, 'etiqueta': etiqueta, 'texto': texto, 'frase': frase}


MAX_PERSONAS_HABLADAS = 5


def esfera_me_deben(usuario, personas, simbolo='$'):
    deudores = sorted((p for p in personas if p.total_pendiente > 0),
                      key=lambda p: p.total_pendiente, reverse=True)
    if not deudores:
        texto = 'Nadie te debe plata ahora.'
        return {'estado': 'verde', 'etiqueta': 'Nadie te debe', 'texto': texto, 'frase': texto}

    total = sum(float(p.total_pendiente) for p in deudores)
    n = len(deudores)
    texto = (f'{n} {_plural(n, "persona te debe", "personas te deben")} '
             f'{money(total, simbolo)} en total.')

    partes = [f'{p.nombre} te debe {_hablado(p.total_pendiente, usuario)}'
              for p in deudores[:MAX_PERSONAS_HABLADAS]]
    resto = n - len(partes)
    detalle = '. '.join(partes) + '.'
    if resto:
        detalle += f' Y {resto} {_plural(resto, "persona más", "personas más")}.'
    frase = f'Te deben {_hablado(total, usuario)} en total. {detalle}'

    return {'estado': 'amarillo', 'etiqueta': 'Por cobrar', 'texto': texto, 'frase': frase}
