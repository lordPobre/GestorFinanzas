"""
Template tag para formatear montos con la moneda del usuario.
Uso en template:  {% load moneda %}  →  {{ monto|money:simbolo_moneda }}
"""
from django import template

register = template.Library()


@register.filter
def money(valor, simbolo='$'):
    """Formatea un número como moneda: 1234567 → $1.234.567"""
    try:
        num = float(valor)
    except (ValueError, TypeError):
        return f"{simbolo}0"

    # Separador de miles con punto (formato es-CL / es-AR)
    entero = int(round(num))
    formateado = f"{entero:,}".replace(',', '.')
    return f"{simbolo}{formateado}"


@register.filter
def money_signed(valor, simbolo='$'):
    """Como money pero con signo +/- adelante (para ingresos/gastos)."""
    try:
        num = float(valor)
    except (ValueError, TypeError):
        return f"{simbolo}0"
    signo = '+' if num >= 0 else '-'
    entero = abs(int(round(num)))
    formateado = f"{entero:,}".replace(',', '.')
    return f"{signo}{simbolo}{formateado}"
