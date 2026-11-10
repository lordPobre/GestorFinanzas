from datetime import date
from decimal import Decimal, InvalidOperation

from django import template

from .. import fechas

register = template.Library()


def _campo(obj, nombre):
    if isinstance(obj, dict):
        return obj.get(nombre)
    return getattr(obj, nombre, None)


def _numero(valor):
    try:
        return Decimal(str(valor or 0))
    except (InvalidOperation, ValueError):
        return Decimal('0')


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
