import re

BASE = (
    'cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
    'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete',
    'dieciocho', 'diecinueve', 'veinte', 'veintiuno', 'veintidós', 'veintitrés',
    'veinticuatro', 'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve',
)
DECENAS = {3: 'treinta', 4: 'cuarenta', 5: 'cincuenta', 6: 'sesenta',
           7: 'setenta', 8: 'ochenta', 9: 'noventa'}
CENTENAS = ('', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos',
            'seiscientos', 'setecientos', 'ochocientos', 'novecientos')

SINGULAR = {'pesos': 'peso', 'dólares': 'dólar', 'euros': 'euro', 'soles': 'sol', 'reales': 'real',
            'centavos': 'centavo'}
MONEDAS = frozenset(SINGULAR) | frozenset(SINGULAR.values())
MASCULINOS = MONEDAS | frozenset({
    'servicio', 'servicios', 'pago', 'pagos', 'mes', 'meses', 'día', 'días', 'año', 'años',
    'movimiento', 'movimientos', 'gasto', 'gastos', 'ingreso', 'ingresos', 'préstamo', 'préstamos',
})
FEMENINOS = frozenset({
    'compra', 'compras', 'cuota', 'cuotas', 'persona', 'personas', 'suscripción',
    'suscripciones', 'meta', 'metas', 'semana', 'semanas', 'vez', 'veces', 'deuda', 'deudas',
})

NOMBRES = {
    'US$': 'dólares', 'USD': 'dólares', 'R$': 'reales', 'BRL': 'reales', 'S/': 'soles', 'PEN': 'soles',
    '€': 'euros', 'EUR': 'euros', 'CLP': 'pesos', 'ARS': 'pesos', 'MXN': 'pesos', 'COP': 'pesos',
}

PORCENTAJE = re.compile(r'(\d)\s?%')
NUMERO = re.compile(r'(?<![\w.,])(\d{1,3}(?:\.\d{3})+|\d+)(?!\w|[.,]\d)(?:(\s+)([^\W\d_]+))?')
MONTO = re.compile(r'(?<![\w$/])(-\s?)?(US\$|R\$|S/|USD|BRL|PEN|EUR|CLP|ARS|MXN|COP|€|\$)\s?'
                   r'(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?(?![.,]?\d)(?![^\W\d_])'
                   r'(\s+(?:de\s+)?[^\W\d_]+)?')


def _hasta_999(n):
    if n < 30:
        return BASE[n]
    if n < 100:
        d, u = divmod(n, 10)
        return DECENAS[d] + (f' y {BASE[u]}' if u else '')
    if n == 100:
        return 'cien'
    c, r = divmod(n, 100)
    return CENTENAS[c] + (f' {_hasta_999(r)}' if r else '')


def _apocope(texto):
    if texto.endswith('veintiuno'):
        return texto[:-9] + 'veintiún'
    if texto.endswith('uno'):
        return texto[:-3] + 'un'
    return texto


def en_palabras(n):
    n = int(n)
    if n == 0:
        return 'cero'
    partes = []
    millones, resto = divmod(n, 1_000_000)
    if millones:
        partes.append('un millón' if millones == 1 else f'{_apocope(en_palabras(millones))} millones')
    miles, unidades = divmod(resto, 1000)
    if miles:
        partes.append('mil' if miles == 1 else f'{_apocope(_hasta_999(miles))} mil')
    if unidades:
        partes.append(_hasta_999(unidades))
    return ' '.join(partes)


def _reemplazo(m):
    n = int(m.group(1).replace('.', ''))
    palabras = en_palabras(n)
    espacio, siguiente = m.group(2), m.group(3)
    if not siguiente:
        return palabras
    clave = siguiente.lower()
    if palabras.endswith('uno'):
        if clave in FEMENINOS:
            palabras = palabras[:-1] + 'a'
        elif clave in MASCULINOS:
            palabras = _apocope(palabras)
    if n == 1 and clave in SINGULAR:
        siguiente = SINGULAR[clave]
    if n >= 1_000_000 and n % 1_000_000 == 0 and clave in MONEDAS:
        espacio = ' de '
    return f'{palabras}{espacio}{siguiente}'


def _monto(m, pesos):
    menos, simbolo, entero, decimales, cola = m.groups()
    cola = cola or ''
    if cola and cola.split()[-1].lower() in MONEDAS:
        base, cola = entero + cola, ''
    else:
        base = f'{entero} {pesos if simbolo == "$" else NOMBRES[simbolo]}'
    if decimales and int(decimales):
        base += f' con {int(decimales.ljust(2, "0"))} centavos'
    return f'{"menos " if menos else ""}{base}{cola}'


def para_voz(texto, pesos='pesos'):
    texto = MONTO.sub(lambda m: _monto(m, pesos), texto or '')
    texto = PORCENTAJE.sub(r'\1 por ciento', texto)
    return NUMERO.sub(_reemplazo, texto)
