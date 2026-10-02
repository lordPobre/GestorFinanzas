from datetime import date

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

    ingresos = float(resumen['ingresos'])
    limite = float(presupuesto.limite_mensual) if presupuesto and presupuesto.limite_mensual else 0

    if limite > 0 and (ingresos <= 0 or limite <= ingresos):
        base = limite
        de_que = 'de tu presupuesto'
    elif ingresos > 0:
        base = ingresos
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
            texto = f'Llevas {money(gastado, simbolo)} {de_que} ({money(base, simbolo)}). Te quedan {queda} para el mes.'
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


MAX_SUSCRIPCIONES_HABLADAS = 8


def esfera_suscripciones(usuario, activas, simbolo='$'):
    if not activas:
        texto = 'No tienes suscripciones activas.'
        return {'estado': 'verde', 'etiqueta': 'Sin suscripciones', 'texto': texto, 'frase': texto}

    orden = sorted(activas, key=lambda s: float(s.monto), reverse=True)
    total = sum(float(s.monto) for s in activas)
    n = len(activas)
    atrasadas = [s for s in activas if s.periodos_atrasados]
    pendientes = [s for s in activas if not s.pagada_este_mes]
    servicios = _plural(n, 'servicio', 'servicios')

    texto = f'Estás suscrito a {n} {servicios} por {money(total, simbolo)} al mes.'
    partes = [f'{s.nombre}, {_hablado(s.monto, usuario)}' for s in orden[:MAX_SUSCRIPCIONES_HABLADAS]]
    resto = n - len(partes)
    detalle = '; '.join(partes) + '.'
    if resto:
        detalle += f' Y {resto} {_plural(resto, "más", "más")}.'
    frase = f'Estás suscrito a {n} {servicios}: {detalle} En total pagas {_hablado(total, usuario)} al mes.'

    if atrasadas:
        k = len(atrasadas)
        monto = sum(float(s.monto_atrasado) for s in atrasadas)
        estado, etiqueta = 'rojo', _plural(k, 'Una atrasada', 'Atrasadas')
        texto += f' {_plural(k, "Una está atrasada", f"{k} están atrasadas")}.'
        nombres = ', '.join(s.nombre for s in atrasadas[:3])
        frase += f' {_plural(k, "Tienes atrasada", "Tienes atrasadas")} {nombres}, por {_hablado(monto, usuario)}.'
    elif pendientes:
        k = len(pendientes)
        monto = sum(float(s.monto) for s in pendientes)
        estado, etiqueta = 'amarillo', 'Falta pagar'
        texto += f' Te falta pagar {money(monto, simbolo)} este mes.'
        frase += f' Este mes te falta pagar {_hablado(monto, usuario)} en {k} {_plural(k, "suscripción", "suscripciones")}.'
    else:
        estado, etiqueta = 'verde', 'Al día'
        frase += ' Este mes ya pagaste todas.'

    return {'estado': estado, 'etiqueta': etiqueta, 'texto': texto, 'frase': frase}


MAX_METAS_HABLADAS = 5
UMBRAL_METAS_VERDE = 70


def esfera_metas(usuario, metas, simbolo='$'):
    if not metas:
        texto = 'Todavía no tienes metas de ahorro.'
        return {'estado': 'neutro', 'etiqueta': 'Sin metas', 'texto': texto, 'frase': texto}

    hoy = date.today()
    ahorrado = sum(float(m.monto_actual) for m in metas)
    objetivo = sum(float(m.monto_meta) for m in metas)
    pct = min(100, round(ahorrado / objetivo * 100)) if objetivo else 0
    vencidas = [m for m in metas if not m.esta_completa and m.fecha_limite and m.fecha_limite < hoy]

    n = len(metas)
    texto = f'Llevas el {pct}% de tus metas: {money(ahorrado, simbolo)} de {money(objetivo, simbolo)}.'
    if n == 1:
        frase = f'Llevas el {pct} por ciento de tu meta {metas[0].nombre}: {_hablado(ahorrado, usuario)} de {_hablado(objetivo, usuario)}.'
    else:
        frase = f'Llevas el {pct} por ciento de tus metas: {_hablado(ahorrado, usuario)} de {_hablado(objetivo, usuario)}.'
        orden = sorted(metas, key=lambda m: float(m.porcentaje), reverse=True)
        partes = []
        for m in orden[:MAX_METAS_HABLADAS]:
            if m.esta_completa:
                partes.append(f'{m.nombre} ya está cumplida')
            else:
                partes.append(f'{m.nombre} va en {round(float(m.porcentaje))} por ciento')
        frase += ' ' + '. '.join(partes) + '.'
        resto = n - len(partes)
        if resto:
            frase += f' Y {resto} {_plural(resto, "meta más", "metas más")}.'

    if vencidas:
        estado, etiqueta = 'rojo', _plural(len(vencidas), 'Meta vencida', 'Metas vencidas')
        nombres = ', '.join(m.nombre for m in vencidas[:3])
        texto += f' Se pasó la fecha de {nombres}.'
        frase += f' Se pasó la fecha de {nombres}.'
    elif pct >= UMBRAL_METAS_VERDE:
        estado, etiqueta = 'verde', 'Casi llegas' if pct < 100 else 'Metas cumplidas'
    else:
        estado, etiqueta = 'amarillo', 'En camino'
        faltan = objetivo - ahorrado
        texto += f' Te faltan {money(faltan, simbolo)}.'
        frase += f' Te faltan {_hablado(faltan, usuario)}.'

    return {'estado': estado, 'etiqueta': etiqueta, 'texto': texto, 'frase': frase}
