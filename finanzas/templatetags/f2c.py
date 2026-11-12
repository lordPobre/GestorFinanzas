import colorsys
from datetime import date
from decimal import Decimal, InvalidOperation

from django import template
from django.utils import timezone
from django.utils.formats import date_format

from .. import fechas
from ..categorias_base import BASE
from ..servicios.mes import MESES_LARGOS
from ..servicios import borrar_mes, vida_2c
from ..servicios.mes_elegido import mes_pedido, selector_mes

register = template.Library()

SUAVES = {
    'verde': ('#E1EDE3', '#1F6B3F'),
    'coral': ('#F5E1D6', '#A4482A'),
    'azul': ('#DFE6F1', '#2F4F86'),
    'lila': ('#EAE2F0', '#5B3F7A'),
    'rosa': ('#F3E3E6', '#9A3550'),
    'ambar': ('#F2EAD3', '#7A5A12'),
    'gris': ('#E7E3DC', '#5A5248'),
}

TONO_BASE = {
    '#60a5fa': 'verde',
    '#53d258': 'azul',
    '#818cf8': 'ambar',
    '#fbbf24': 'coral',
    '#22d3ee': 'rosa',
    '#f472b6': 'rosa',
    '#2dd4bf': 'lila',
    '#38bdf8': 'azul',
    '#c084fc': 'lila',
    '#facc15': 'ambar',
    '#8b8b96': 'gris',
    '#fb923c': 'coral',
    '#e25c5c': 'azul',
}

ICONOS_BASE = {fila[0]: fila[4] for fila in BASE}

TONOS_PERSONA = ('coral', 'azul', 'lila', 'verde', 'ambar', 'rosa')

MESES_ES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
            'octubre', 'noviembre', 'diciembre')

PASOS_VISIBLES = 6

COLORES_TOPE = {'rojo': '#C2412D', 'amarillo': '#C98A1B', 'verde': '#0D6E55'}

SALUDOS = ((6, 12, 'Buenos días', 'fa-sun', 'dia'), (12, 20, 'Buenas tardes', 'fa-cloud-sun', 'tarde'))
NOCHE = {'texto': 'Buenas noches', 'icono': 'fa-moon', 'tono': 'noche'}


def _campo(obj, nombre):
    if isinstance(obj, dict):
        return obj.get(nombre)
    return getattr(obj, nombre, None)


def _numero(valor):
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def tono_suave(color):
    texto = str(color or '').strip().lower()
    if texto in TONO_BASE:
        return TONO_BASE[texto]
    texto = texto.lstrip('#')
    if len(texto) == 3:
        texto = ''.join(c * 2 for c in texto)
    if len(texto) < 6:
        return 'gris'
    try:
        r, g, b = (int(texto[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 'gris'
    h, luz, s = colorsys.rgb_to_hls(r, g, b)
    if s < .18 or luz > .92 or luz < .12:
        return 'gris'
    grados = h * 360
    if grados < 30 or grados >= 345:
        return 'coral'
    if grados < 65:
        return 'ambar'
    if grados < 165:
        return 'verde'
    if grados < 250:
        return 'azul'
    if grados < 290:
        return 'lila'
    return 'rosa'


@register.filter
def fondo_suave(color):
    return SUAVES[tono_suave(color)][0]


@register.filter
def tinta_suave(color):
    return SUAVES[tono_suave(color)][1]


@register.filter
def paleta_suave(paleta):
    vistos = set()
    salida = []
    for fila in paleta or []:
        hex_ = fila[0]
        nombre = fila[1] if len(fila) > 1 else ''
        tono = tono_suave(hex_)
        if tono in vistos:
            continue
        vistos.add(tono)
        salida.append((hex_, nombre, SUAVES[tono][0], SUAVES[tono][1]))
    return salida


@register.filter
def icono_cat(slug, defecto='fa-tag'):
    return ICONOS_BASE.get(str(slug or ''), defecto)


@register.simple_tag
def tope_de(topes, slug, gastado):
    fila = (topes or {}).get(slug) if isinstance(topes, dict) else None
    if not fila or len(fila) < 2:
        return None
    monto = _numero(fila[1])
    if monto <= 0:
        return None
    total = _numero(gastado)
    pct = round(total / monto * 100)
    tono = 'rojo' if pct >= 100 else 'amarillo' if pct >= 80 else 'verde'
    return {'pct': pct, 'ancho': max(0, min(100, pct)), 'tono': tono, 'color': COLORES_TOPE[tono],
            'exceso': max(Decimal('0'), total - monto), 'tope': monto}


@register.filter
def pasados(items, cuantos=5):
    hoy = fechas.hoy()
    salida = []
    for t in items or []:
        if _campo(t, 'por_pagar'):
            continue
        fecha = _campo(t, 'fecha')
        if isinstance(fecha, date) and fecha > hoy:
            continue
        salida.append(t)
        if len(salida) >= int(cuantos):
            break
    return salida


@register.filter
def corto(valor, simbolo='$'):
    n = abs(_numero(valor))
    signo = '-' if _numero(valor) < 0 else ''
    if n >= 1000000:
        texto = f'{n / 1000000:.1f}'.rstrip('0').rstrip('.').replace('.', ',') + ' M'
    elif n >= 10000:
        texto = f'{round(n / 1000)} mil'
    else:
        texto = f'{round(n):,}'.replace(',', '.')
    return f'{signo}{simbolo or "$"}{texto}'


@register.filter
def inicial(texto):
    texto = str(texto or '').strip()
    return texto[:1].upper() or '?'


@register.filter
def tope_pct(valor, tope):
    t = _numero(tope)
    if t <= 0:
        return 0
    return max(0, min(100, round(_numero(valor) / t * 100)))


def _mes_y_anio(etiqueta):
    trozos = str(etiqueta or '').strip().lower().split()
    if len(trozos) == 2 and trozos[0] in MESES_LARGOS and trozos[1].isdigit():
        return MESES_LARGOS.index(trozos[0]), trozos[1]
    return None, ''


@register.simple_tag
def barras(etiquetas, valores, cuantos=6, elegido=None):
    pares = list(zip(etiquetas or [], valores or [], strict=False))
    clave = str(elegido or '').strip().lower()
    fin = len(pares)
    for i, (e, _) in enumerate(pares):
        if clave and str(e).strip().lower() == clave:
            fin = i + 1
            break
    pares = pares[max(0, fin - int(cuantos)):fin]
    tope = max([_numero(v) for _, v in pares] + [Decimal('1')])
    ultimo = len(pares) - 1
    salida, anio_previo = [], None
    for i, (e, v) in enumerate(pares):
        mes, anio = _mes_y_anio(e)
        salida.append({
            'etiqueta': str(e),
            'corta': MESES_LARGOS[mes][:3].capitalize() if mes is not None else str(e),
            'anio': anio if anio and anio != anio_previo else '',
            'valor': _numero(v),
            'alto': max(4, round(_numero(v) / tope * 100)) if _numero(v) else 4,
            'actual': i == ultimo,
        })
        anio_previo = anio
    return salida


@register.simple_tag(takes_context=True)
def mes_de_pagina(context):
    request = context.get('request')
    usuario = getattr(request, 'user', None)
    if request is None or not getattr(usuario, 'is_authenticated', False):
        return None
    hoy = fechas.hoy()
    year, month = mes_pedido(request, hoy)
    return selector_mes(usuario, year, month, hoy)


@register.simple_tag
def mas_cara(subs, total):
    activas = [s for s in subs or [] if _campo(s, 'activa')]
    if len(activas) < 2:
        return None
    top = max(activas, key=lambda s: _numero(_campo(s, 'monto')))
    monto = _numero(_campo(top, 'monto'))
    t = _numero(total)
    return {'nombre': _campo(top, 'nombre'), 'anual': monto * 12, 'pct': round(monto / t * 100) if t > 0 else 0}


@register.filter
def tono_nombre(texto):
    return TONOS_PERSONA[sum(ord(c) for c in str(texto or '')) % len(TONOS_PERSONA)]


def _mas_meses(year, month, cuantos):
    total = year * 12 + (month - 1) + cuantos
    return total // 12, total % 12 + 1


@register.filter
def pr_mes(persona):
    hoy = fechas.hoy()
    return sum((p.falta_este_mes(hoy.year, hoy.month) for p in persona.prestamos.all()), Decimal('0'))


@register.simple_tag
def prestamos_mes(personas):
    quienes = []
    for persona in personas or []:
        monto = pr_mes(persona)
        if monto > 0:
            quienes.append({'nombre': persona.nombre, 'monto': monto})
    return {'total': sum((q['monto'] for q in quienes), Decimal('0')), 'quienes': quienes}


def _pasos_unico(prestamo, debo):
    abonado = prestamo.total_abonado
    pendiente = max(Decimal('0'), prestamo.monto_pendiente)
    ultimo = next(iter(prestamo.abonos.all()), None)
    devuelto = {
        'estado': 'pagada' if abonado > 0 else 'viene',
        'etq': 'Le pagaste' if debo else 'Te devolvió',
        'monto': abonado,
        'nota': date_format(ultimo.fecha, 'j b') if ultimo else 'Nada todavía',
        'icono': 'fa-check' if abonado > 0 else 'fa-circle',
        'corto': 'Pagado' if debo else 'Devuelto',
    }
    falta = {
        'estado': 'mes' if pendiente > 0 else 'pagada',
        'etq': 'Falta',
        'monto': pendiente,
        'nota': 'De una vez' if pendiente > 0 else 'Nada',
        'icono': 'fa-clock' if pendiente > 0 else 'fa-check',
        'corto': 'Falta' if pendiente > 0 else 'Listo',
    }
    return {'pasos': [devuelto, falta], 'antes': 0, 'mas': 0}


@register.simple_tag
def pr_pasos(prestamo, debo=False):
    if prestamo.tipo != 'CUOTAS':
        return _pasos_unico(prestamo, debo)
    hoy = fechas.hoy()
    total = max(1, int(prestamo.cuotas_totales or 1))
    abonadas = prestamo.cuotas_abonadas
    cuota = prestamo.monto_cuota
    empieza = 0 if prestamo.falta_este_mes(hoy.year, hoy.month) > 0 else 1
    inicio = 0
    if total > PASOS_VISIBLES:
        inicio = max(0, min(abonadas - 1, total - PASOS_VISIBLES))
    pasos = []
    for i in range(inicio, min(total, inicio + PASOS_VISIBLES)):
        if i < abonadas:
            pasos.append({'estado': 'pagada', 'etq': f'Cuota {i + 1}', 'monto': cuota,
                          'nota': 'Pagada' if debo else 'Te la pagó', 'icono': 'fa-check', 'corto': str(i + 1)})
            continue
        desfase = i - abonadas + empieza
        year, month = _mas_meses(hoy.year, hoy.month, desfase)
        nombre = MESES_ES[month - 1]
        if desfase == 0:
            dia = prestamo.dia_de_pago(year, month).day
            pasos.append({'estado': 'mes', 'etq': f'Cuota {i + 1}', 'monto': cuota,
                          'nota': f'Vence el {dia} {nombre[:3]}', 'icono': 'fa-clock',
                          'corto': nombre[:3].capitalize()})
        else:
            nota = nombre.capitalize() + (f' {year}' if year != hoy.year else '')
            pasos.append({'estado': 'viene', 'etq': f'Cuota {i + 1}', 'monto': cuota, 'nota': nota,
                          'icono': 'fa-circle', 'corto': nombre[:3].capitalize()})
    return {'pasos': pasos, 'antes': inicio, 'mas': max(0, total - inicio - PASOS_VISIBLES)}


@register.simple_tag
def pr_abonos(persona, cuantos=8):
    filas = []
    for p in persona.prestamos.all():
        for a in p.abonos.all():
            filas.append({'monto': a.monto, 'fecha': a.fecha, 'nota': a.nota, 'prestamo': p.descripcion,
                          'orden': (a.fecha, a.pk)})
    filas.sort(key=lambda f: f['orden'], reverse=True)
    return filas[:int(cuantos)]


def saludo_de(hora):
    for desde, hasta, texto, icono, tono in SALUDOS:
        if desde <= hora < hasta:
            return {'texto': texto, 'icono': icono, 'tono': tono}
    return dict(NOCHE)


@register.simple_tag
def saludo_hora():
    return saludo_de(timezone.localtime().hour)


@register.filter
def nombre_corto(texto):
    partes = str(texto or '').split()
    return partes[0] if partes else ''


def _dias_hasta(fecha):
    if not isinstance(fecha, date):
        return None
    return (fecha - fechas.hoy()).days


@register.filter
def en_dias(fecha):
    dias = _dias_hasta(fecha)
    if dias is None or dias < 0:
        return ''
    if dias == 0:
        return 'Hoy'
    if dias == 1:
        return 'Mañana'
    return f'En {dias} días'


@register.filter
def pronto(fecha):
    dias = _dias_hasta(fecha)
    return dias is not None and 0 <= dias <= 3


@register.filter
def suma_gastos(movimientos):
    return sum((_numero(_campo(t, 'monto')) for t in movimientos or [] if not _campo(t, 'es_ingreso')),
               Decimal('0'))


@register.simple_tag
def metas_2c(datos):
    return vida_2c.metas_2c(list(datos or []), fechas.hoy())


@register.simple_tag
def barras_dobles(meses, ingresos, gastos, cuantos=6, elegido=None):
    return vida_2c.barras_dobles(meses, ingresos, gastos, cuantos, elegido, fechas.hoy())


def _usuario_de(context):
    request = context.get('request')
    usuario = getattr(request, 'user', None)
    if request is None or not getattr(usuario, 'is_authenticated', False):
        return request, None
    return request, usuario


@register.simple_tag(takes_context=True)
def ranking_2c(context, ranking):
    request, usuario = _usuario_de(context)
    if usuario is None:
        return list(ranking or [])
    year, month = mes_pedido(request, fechas.hoy())[:2]
    return vida_2c.series_categorias(usuario, list(ranking or []), year, month)


@register.simple_tag(takes_context=True)
def anotado_6m(context):
    _, usuario = _usuario_de(context)
    if usuario is None:
        return []
    return vida_2c.anotado_por_mes(usuario, fechas.hoy())


@register.simple_tag
def flujo_2c(analisis):
    return vida_2c.flujo(_campo(analisis, 'ingreso_mensual'), _campo(analisis, 'gasto_mensual'),
                         _campo(analisis, 'compromisos_mes'))


@register.simple_tag
def gastos_borrables(movimientos):
    return borrar_mes.resumen(movimientos)


@register.simple_tag(takes_context=True)
def borrado_pendiente(context):
    sesion = getattr(context.get('request'), 'session', None)
    if sesion is None:
        return None
    return sesion.pop('borrado_mes', None)
