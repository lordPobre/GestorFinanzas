from decimal import ROUND_HALF_UP, Decimal


def a_decimal(valor):
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0))


def suma(valores):
    total = Decimal(0)
    for v in valores:
        total += a_decimal(v)
    return total


def redondear(valor, decimales=0):
    exacto = a_decimal(valor).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    return int(exacto) if decimales == 0 else exacto
