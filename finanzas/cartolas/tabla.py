"""Cartolas exportadas como CSV o Excel.

Un PDF esconde las columnas: al extraer el texto, la que viene vacía
desaparece. Una exportación tabular no tiene ese problema — cada celda sabe
a qué columna pertenece — así que acá el trabajo no es deducir el signo sino
reconocer cómo llamó cada banco a sus columnas.
"""
import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal

from .base import Cartola, ErrorCartola, MovimientoLeido, plata

MAX_FILAS = 5000

MES_ABREV = {
    'ene': 1, 'jan': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'apr': 4, 'may': 5,
    'jun': 6, 'jul': 7, 'ago': 8, 'aug': 8, 'sep': 9, 'set': 9, 'oct': 10,
    'nov': 11, 'dic': 12, 'dec': 12,
}

COLUMNAS = (
    ('fecha', ('fecha', 'fecha transaccion', 'fecha transacción', 'fecha contable',
               'fecha operacion', 'fecha operación', 'fecha movimiento', 'dia', 'día',
               'date', 'fecha de transaccion', 'fecha de transacción')),
    ('descripcion', ('descripcion', 'descripción', 'detalle', 'glosa', 'movimiento',
                     'concepto', 'comercio', 'descripcion movimiento',
                     'descripción movimiento', 'detalle movimiento', 'referencia',
                     'description')),
    ('cargo', ('cargo', 'cargos', 'cargo $', 'debito', 'débito', 'debitos', 'débitos',
               'giro', 'giros', 'monto cargo', 'egreso', 'egresos', 'pagos')),
    ('abono', ('abono', 'abonos', 'abono $', 'credito', 'crédito', 'creditos',
               'créditos', 'deposito', 'depósito', 'depositos', 'depósitos',
               'monto abono', 'ingreso', 'ingresos')),
    ('monto', ('monto', 'monto $', 'monto total', 'valor', 'importe', 'total',
               'amount')),
    ('saldo', ('saldo', 'saldo $', 'saldo contable', 'saldo disponible', 'balance')),
)

NO_ES_FILA = ('saldo inicial', 'saldo anterior', 'saldo final', 'total cargos',
              'total abonos', 'totales', 'subtotal')


def es_tabla(nombre):
    return bool(re.search(r'\.(csv|tsv|txt|xlsx|xlsm)$', (nombre or ''), re.I))


def leer_tabla(binario, nombre=''):
    filas = (_de_excel(binario) if re.search(r'\.(xlsx|xlsm)$', nombre or '', re.I)
             else _de_csv(binario))
    if not filas:
        raise ErrorCartola(
            'El archivo no tiene filas. Si lo exportaste del banco, súbelo tal '
            'como quedó, sin abrirlo ni volver a guardarlo.')

    cabecera, columnas = _cabecera(filas)
    if cabecera is None:
        raise ErrorCartola(
            'No reconocí las columnas de este archivo. Necesito al menos una '
            'columna de fecha y una de monto (o de cargos y abonos). Si es una '
            'exportación del banco sin editar, mándamela y agrego el formato.')

    movimientos = _movimientos(filas[cabecera + 1:], columnas)
    if len(movimientos) < 2:
        raise ErrorCartola(
            'Encontré las columnas pero ninguna fila con fecha y monto. '
            'Revisa que el archivo traiga el detalle de movimientos.')

    cartola = Cartola(
        banco=_banco(filas, nombre),
        movimientos=movimientos,
        periodo=_periodo(movimientos),
        saldo_final=movimientos[0].saldo or None,
    )
    cartola.nota_cuadre = _verificar(cartola, columnas)
    return cartola


def _de_csv(binario):
    crudo = binario.read()
    if isinstance(crudo, str):
        crudo = crudo.encode('utf-8')
    texto = None
    for codec in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            texto = crudo.decode(codec)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise ErrorCartola('No pude leer el texto del archivo.')

    muestra = texto[:4000]
    delim = max((';', ',', '\t', '|'), key=muestra.count)
    lector = csv.reader(io.StringIO(texto), delimiter=delim)
    filas = []
    for i, fila in enumerate(lector):
        if i >= MAX_FILAS:
            break
        filas.append([(c or '').strip() for c in fila])
    return filas


def _de_excel(binario):
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ErrorCartola(
            'Falta la librería para leer Excel. Guarda el archivo como CSV y '
            'súbelo así.')
    try:
        libro = load_workbook(binario, read_only=True, data_only=True)
    except Exception:
        raise ErrorCartola('No se pudo abrir el Excel. ¿Seguro que es el archivo '
                           'que exportó el banco?')
    hoja = libro[libro.sheetnames[0]]
    filas = []
    for i, fila in enumerate(hoja.iter_rows(values_only=True)):
        if i >= MAX_FILAS:
            break
        filas.append([_celda(c) for c in fila])
    libro.close()
    return filas


def _celda(valor):
    if valor is None:
        return ''
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _normal(txt):
    t = (txt or '').lower().strip()
    t = re.sub(r'[\n\r]+', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return re.sub(r'[.:()°º*]', '', t).strip()


def _cabecera(filas):
    for i, fila in enumerate(filas[:40]):
        columnas = {}
        for j, celda in enumerate(fila):
            clave = _columna(_normal(celda))
            if clave and clave not in columnas:
                columnas[clave] = j
        tiene_plata = any(k in columnas for k in ('monto', 'cargo', 'abono'))
        if 'fecha' in columnas and tiene_plata:
            return i, columnas
    return None, {}


def _columna(nombre):
    if not nombre:
        return ''
    for clave, alias in COLUMNAS:
        if nombre in alias:
            return clave
    for clave, alias in COLUMNAS:
        if any(nombre.startswith(a) for a in alias):
            return clave
    return ''


def _movimientos(filas, col):
    leidos = []
    for fila in filas:
        if not fila:
            continue
        texto = ' '.join(str(c) for c in fila).lower()
        if any(p in texto for p in NO_ES_FILA):
            continue

        fecha = _fecha(_dato(fila, col.get('fecha')))
        if not fecha:
            continue

        cargo = _cifra(_dato(fila, col.get('cargo')))
        abono = _cifra(_dato(fila, col.get('abono')))
        monto = _cifra(_dato(fila, col.get('monto')))
        saldo = _cifra(_dato(fila, col.get('saldo')))

        if cargo:
            valor, tipo = abs(cargo), 'EGRESO'
        elif abono:
            valor, tipo = abs(abono), 'INGRESO'
        elif monto:
            valor = abs(monto)
            tipo = 'EGRESO' if monto < 0 else 'INGRESO'
        else:
            continue

        leidos.append(MovimientoLeido(
            fecha=fecha,
            descripcion=' '.join((_dato(fila, col.get('descripcion')) or '').split())[:200],
            monto=valor, tipo=tipo, saldo=saldo or Decimal(0),
        ))

    if len(leidos) > 1 and leidos[0].fecha < leidos[-1].fecha:
        leidos.reverse()

    if 'cargo' not in col and 'abono' not in col and 'saldo' in col:
        _signos_por_saldo(leidos)
    return leidos


def _signos_por_saldo(movimientos):
    """Una sola columna de monto, sin signo: lo decide la cadena de saldos."""
    for i, m in enumerate(movimientos):
        if i + 1 >= len(movimientos):
            continue
        previo = movimientos[i + 1].saldo
        if previo is None:
            continue
        delta = m.saldo - previo
        if delta:
            m.tipo = 'INGRESO' if delta > 0 else 'EGRESO'
            if abs(delta) != m.monto:
                m.aviso = 'El saldo no calza con el monto de esta fila. Revísala.'


def _dato(fila, i):
    if i is None or i >= len(fila):
        return ''
    return str(fila[i] or '').strip()


def _cifra(txt):
    if not txt:
        return None
    limpio = txt.replace(' ', '')
    negativo = limpio.startswith('-') or (limpio.startswith('(') and limpio.endswith(')'))
    valor = plata(limpio)
    if not valor:
        return None
    valor = abs(valor)
    return -valor if negativo else valor


def _fecha(txt):
    if not txt:
        return None
    t = txt.strip()

    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', t)
    if m:
        return _armar(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = re.match(r'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', t)
    if m:
        return _armar(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = re.match(r'^(\d{1,2})[\s/.-]*([a-zA-Z]{3,10})\.?[\s/.-]*(\d{2,4})', t)
    if m:
        mes = MES_ABREV.get(m.group(2)[:3].lower())
        if mes:
            return _armar(int(m.group(1)), mes, int(m.group(3)))
    return None


def _armar(dia, mes, anio):
    if anio < 100:
        anio += 2000
    try:
        return date(anio, mes, dia)
    except ValueError:
        try:
            return date(anio, dia, mes)
        except ValueError:
            return None


def _verificar(cartola, columnas):
    n = len(cartola.movimientos)
    marcados = [m for m in cartola.movimientos if m.aviso]

    if marcados:
        cartola.cuadra = False
        return (f'{len(marcados)} de {n} filas no calzan con la cadena de saldos. '
                f'Revísalas antes de guardar.')

    cartola.cuadra = True
    if 'cargo' in columnas or 'abono' in columnas:
        return (f'{n} movimientos leídos de columnas separadas de cargos y abonos: '
                f'el signo viene del archivo, no de un cálculo.')
    if 'saldo' in columnas:
        return (f'Los saldos de las {n} filas forman una cadena continua: los '
                f'montos y los signos son correctos.')
    return (f'{n} movimientos leídos de la columna de monto, con el signo que '
            f'trae el archivo. Revisa que estén todos antes de guardar.')


def _banco(filas, nombre):
    texto = ' '.join(' '.join(str(c) for c in f) for f in filas[:12]).lower()
    conocidos = (
        ('santander', 'Banco Santander'), ('bci', 'Banco BCI'),
        ('bancoestado', 'BancoEstado'), ('banco estado', 'BancoEstado'),
        ('scotiabank', 'Scotiabank'), ('itau', 'Banco Itaú'), ('itaú', 'Banco Itaú'),
        ('falabella', 'Banco Falabella'), ('security', 'Banco Security'),
        ('bice', 'Banco BICE'), ('coopeuch', 'Coopeuch'), ('tenpo', 'Tenpo'),
        ('mach', 'MACH'), ('mercado pago', 'Mercado Pago'),
        ('mercadopago', 'Mercado Pago'), ('global66', 'Global66'),
        ('banco de chile', 'Banco de Chile'), ('chile', 'Banco de Chile'),
    )
    fuente = texto + ' ' + (nombre or '').lower()
    for pista, etiqueta in conocidos:
        if pista in fuente:
            return f'{etiqueta} (archivo exportado)'
    return 'Cartola exportada'


def _periodo(movimientos):
    meses = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
             'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
    if not movimientos:
        return ''
    nueva, vieja = movimientos[0].fecha, movimientos[-1].fecha
    if (nueva.month, nueva.year) == (vieja.month, vieja.year):
        return f'{meses[nueva.month - 1]} {nueva.year}'
    return (f'{meses[vieja.month - 1]} a {meses[nueva.month - 1]} {nueva.year}')
