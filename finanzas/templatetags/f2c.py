import colorsys
from datetime import date
from decimal import Decimal, InvalidOperation

from django import template

from .. import fechas
from ..categorias_base import BASE
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

COLORES_TOPE = {'rojo': '#C2412D', 'amarillo': '#C98A1B', 'verde': '#0D6E55'}


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


@register.simple_tag
def barras(etiquetas, valores, cuantos=6):
    pares = list(zip(etiquetas or [], valores or [], strict=False))[-int(cuantos):]
    tope = max([_numero(v) for _, v in pares] + [Decimal('1')])
    ultimo = len(pares) - 1
    return [{'etiqueta': str(e), 'valor': _numero(v), 'alto': max(4, round(_numero(v) / tope * 100)) if _numero(v) else 4,
             'actual': i == ultimo} for i, (e, v) in enumerate(pares)]


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
