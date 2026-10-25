import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from .. import fechas
from ..cartolas.analisis import categoria_de

MAX_MONTO = Decimal('999999999')
LARGO = 200

MILES = re.compile(r'(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(?:lucas?|luquitas?|k|mil)\b', re.I)
NUMERO = re.compile(r'(?<![\w.,])\$?\s?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?(?![\w.,]?\d)')
DIAS = (('anteayer', 2), ('antier', 2), ('ayer', 1), ('hoy', 0))
DE_INGRESO = ('me pagaron', 'sueldo', 'me depositaron', 'recibí', 'recibi', 'ingreso', 'me transfirieron',
              'me devolvieron')
RELLENO = frozenset('''en de del por para con un una unos unas el la los las al me mi mis
gasté gaste gasto pagué pague pago compré compre anoto anota anotar fue fueron y pesos peso'''.split())


def _cifra(texto):
    try:
        return Decimal(texto.replace('.', '').replace(',', '.'))
    except InvalidOperation:
        return None


def _monto(texto):
    m = MILES.search(texto)
    if m:
        valor = _cifra(m.group(1).replace('.', ','))
        return (valor * 1000 if valor is not None else None), texto[:m.start()] + ' ' + texto[m.end():]
    m = NUMERO.search(texto)
    if m:
        valor = _cifra(m.group(1))
        if valor is not None and m.group(2):
            valor += Decimal(m.group(2).ljust(2, '0')) / 100
        return valor, texto[:m.start()] + ' ' + texto[m.end():]
    return None, texto


def _fecha(texto):
    hoy = fechas.hoy()
    bajo = texto.lower()
    for palabra, atras in DIAS:
        m = re.search(rf'\b{palabra}\b', bajo)
        if m:
            return hoy - timedelta(days=atras), texto[:m.start()] + ' ' + texto[m.end():]
    return hoy, texto


def _descripcion(texto):
    palabras = [p for p in re.split(r'\s+', texto.replace('$', ' ')) if p and p.lower().strip('.,;:') not in RELLENO]
    limpio = ' '.join(palabras).strip(' .,;:-')[:LARGO]
    return limpio[:1].upper() + limpio[1:]


def interpretar(texto, tipo=None):
    original = ' '.join((texto or '').split())[:LARGO]
    monto, resto = _monto(original)
    fecha, resto = _fecha(resto)
    if tipo not in ('INGRESO', 'EGRESO'):
        bajo = original.lower()
        tipo = 'INGRESO' if any(p in bajo for p in DE_INGRESO) else 'EGRESO'
    descripcion = _descripcion(resto)
    claro = monto is not None and 0 < monto <= MAX_MONTO
    return {
        'monto': monto if claro else None,
        'fecha': fecha,
        'tipo': tipo,
        'descripcion': descripcion,
        'categoria': categoria_de(descripcion or original, tipo),
        'claro': claro,
    }
