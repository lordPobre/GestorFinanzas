from decimal import Decimal


def suma(valores):
    total = Decimal(0)
    for v in valores:
        total += v if isinstance(v, Decimal) else Decimal(str(v or 0))
    return total
