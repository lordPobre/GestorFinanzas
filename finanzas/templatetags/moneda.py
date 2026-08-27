"""Formatea montos con la moneda del usuario.

Uso:  {% load moneda %}  →  {{ monto|money }}  o  {{ monto|money:simbolo_moneda }}
"""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

# Monedas que se escriben sin centavos. En CLP y COP los decimales no existen
# en la práctica, así que mostrarlos solo agrega ruido.
SIN_DECIMALES = {'$', 'CLP', 'COP'}


def _separar_miles(entero):
    """1234567 → '1.234.567' (formato es-CL / es-AR / es-CO)."""
    return f'{entero:,}'.replace(',', '.')


@register.filter
def money(valor, simbolo='$'):
    """Formatea un número como moneda: 1234567 → $1.234.567"""
    try:
        num = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return f'{simbolo}0'

    negativo = num < 0
    num = abs(num)

    if simbolo in SIN_DECIMALES:
        texto = _separar_miles(int(num.to_integral_value()))
    else:
        # ANTES: siempre se redondeaba a entero, así que en USD o EUR se
        # perdían los centavos. $12,45 se mostraba como $12.
        entero = int(num)
        centavos = int((num - entero) * 100)
        texto = f'{_separar_miles(entero)},{centavos:02d}'

    return f'{"-" if negativo else ""}{simbolo}{texto}'


@register.filter
def money_signed(valor, simbolo='$'):
    """Como money pero con el signo adelante, para ingresos y gastos."""
    try:
        num = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return f'{simbolo}0'
    signo = '+' if num >= 0 else '-'
    return f'{signo}{money(abs(num), simbolo)}'


@register.filter
def money_corto(valor, simbolo='$'):
    """Versión compacta para etiquetas de gráficos y espacios angostos:
    1234567 → $1,2M · 45000 → $45k

    Existe porque en móvil un monto completo no cabe y se cortaba a mitad.
    """
    try:
        num = float(valor)
    except (ValueError, TypeError):
        return f'{simbolo}0'

    signo = '-' if num < 0 else ''
    num = abs(num)

    if num >= 1_000_000:
        texto = f'{num / 1_000_000:.1f}'.replace('.', ',').rstrip('0').rstrip(',') + 'M'
    elif num >= 1_000:
        texto = f'{num / 1_000:.0f}k'
    else:
        texto = f'{num:.0f}'
    return f'{signo}{simbolo}{texto}'


@register.filter
def pct(parte, total):
    """Porcentaje entero, sin reventar cuando el total es cero.

    widthratio en los templates falla con total=0 y dejaba la barra sin
    ancho o con un error silencioso.
    """
    try:
        parte = float(parte)
        total = float(total)
    except (ValueError, TypeError):
        return 0
    if total <= 0:
        return 0
    return min(100, max(0, round(parte / total * 100)))
