from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

SIN_DECIMALES = {'$', 'CLP', 'COP'}


def _separar_miles(entero):
    return f'{entero:,}'.replace(',', '.')


@register.filter
def money(valor, simbolo='$'):
    try:
        num = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return f'{simbolo}0'

    negativo = num < 0
    num = abs(num)

    if simbolo in SIN_DECIMALES:
        texto = _separar_miles(int(num.to_integral_value()))
    else:
        entero = int(num)
        centavos = int((num - entero) * 100)
        texto = f'{_separar_miles(entero)},{centavos:02d}'

    return f'{"-" if negativo else ""}{simbolo}{texto}'


@register.filter
def money_signed(valor, simbolo='$'):
    try:
        num = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return f'{simbolo}0'
    signo = '+' if num >= 0 else '-'
    return f'{signo}{money(abs(num), simbolo)}'


@register.filter
def money_corto(valor, simbolo='$'):
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
    try:
        parte = float(parte)
        total = float(total)
    except (ValueError, TypeError):
        return 0
    if total <= 0:
        return 0
    return min(100, max(0, round(parte / total * 100)))


@register.filter
def a_json(valor):
    import json
    from decimal import Decimal

    def convertir(o):
        if isinstance(o, Decimal):
            return float(o)
        return str(o)

    if isinstance(valor, str):
        texto = valor.strip()
        if texto.startswith("[") or texto.startswith("{"):
            return texto

    return json.dumps(valor, default=convertir, ensure_ascii=False)
