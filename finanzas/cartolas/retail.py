"""Estados de cuenta de tarjetas de casas comerciales y bancos retail.

OTRO MUNDO QUE EL DE LA CARTOLA
-------------------------------
Una cartola de cuenta corriente lleva saldo corrido y de ahí sale el signo
de cada movimiento. Un estado de cuenta de tarjeta no tiene saldo: tiene
cuotas, y todo es cargo. No hay signo que deducir.

Lo que sí hay que decidir es CUÁNTO importar de cada fila, y ahí está el
error fácil de cometer. Una compra en 12 cuotas aparece en el estado de los
doce meses. Importar el monto completo sería contar hoy una compra del año
pasado, y volver a contarla el mes que viene. Lo que sale de tu bolsillo
este mes es la cuota. Eso es lo que se importa, de cada fila, siempre —
para una compra en una sola cuota la cuota es el monto completo, así que la
regla vale para todas.

CÓMO SE LEE UNA FILA SIN CONOCER EL FORMATO
-------------------------------------------
Los estados de Paris, Ripley, La Polar, Hites, ABCDIN o Tricot imprimen las
mismas columnas en distinto orden y con distintos títulos, pero todos
terminan la fila con el valor que se cobra este mes:

    30/09/2025  FARMACIA X      45.900   3/6   15.300
    12-ago-25   SUPERMERCADO    19.990   1/1   19.990
    05/09/2025  SEGURO CESANTIA                 2.490

La última cifra de la línea es el cargo del período. Es la única regla que
se necesita, y es la que todos cumplen porque la columna final del detalle
es siempre «valor cuota» o «monto a pagar».

LA VERIFICACIÓN
---------------
Que la regla valga no se da por hecho: la suma de todo lo leído tiene que
dar el total que el propio estado declara al final («Monto total facturado»,
«Total a pagar», «Total del período»). Si se aleja más de un 15% el archivo
se rechaza entero; entre 1% y 15% se entrega marcado en rojo para revisar
fila por fila. Sin total declarado se entrega, pero avisando que no hubo
contra qué comprobarlo.

LA FECHA
--------
Una cuota se fecha en el día de facturación, no en el de la compra: la
cuota de agosto es un gasto de agosto aunque la compra sea de septiembre
del año pasado. Las compras de una sola cuota conservan su fecha real.
"""
import re
from datetime import datetime
from decimal import Decimal

from .base import Cartola, ErrorCartola, MovimientoLeido, plata, registrar
from .universal import CIFRA, MES_LETRAS, MESES

FECHA_NUM = re.compile(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b')
FECHA_LETRA = re.compile(r'\b(\d{1,2})[\s/.-]*([a-zA-Z]{3,10})\.?[\s/.-]*(\d{2,4})\b')

# «3/6», «03 de 06», «cuota 3 de 6». El total no pasa de 60 cuotas en ningún
# retail chileno, así que un «2025/2026» no se cuela.
CUOTA = re.compile(r'\b(\d{1,2})\s*(?:/|de)\s*(\d{1,2})\b')

TOTAL = re.compile(
    r'(?:monto\s+total\s+facturado(?:\s+a\s+pagar)?|total\s+facturado|'
    r'total\s+a\s+pagar|monto\s+a\s+pagar|total\s+del\s+per[ií]odo|'
    r'pago\s+total|total\s+compras\s+del\s+per[ií]odo)'
    r'[^\d\-]{0,60}(-?\d[\d.]*(?:,\d{1,2})?)', re.I,
)

FECHA_FACT = re.compile(
    r'fecha\s+(?:de\s+)?facturaci[oó]n[^\d]{0,20}(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
    re.I,
)
VENCE = re.compile(
    r'fecha\s+(?:de\s+)?(?:vencimiento|pago)[^\d]{0,20}(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
    re.I,
)
CONTRATO = re.compile(
    r'(?:n[°ºo]\s*(?:de\s*)?(?:contrato|tarjeta|cuenta)|tarjeta\s+n[°ºo])'
    r'\s*:?\s*([\d*Xx\-]{4,20})', re.I,
)

# Filas que aparecen en el detalle pero no son un gasto del mes.
NO_ES_GASTO = ('pago tarjeta', 'pago recibido', 'abono pago', 'su pago',
               'pago estado anterior', 'pago realizado', 'abono en cuenta',
               'pago normal', 'nota de credito', 'nota de crédito')

# Líneas con fecha y cifras que no son movimientos.
NO_ES_FILA = ('total', 'subtotal', 'saldo', 'cupo', 'página', 'pagina',
              'resumen', 'estado de cuenta', 'fecha de', 'periodo', 'período',
              'vencimiento', 'tasa', 'cae ', 'interés', 'interes total')


class Retail:
    """Motor de estados de cuenta. Los emisores son subclases de una línea."""

    # Lo que separa las dos listas del selector en la pantalla de importar:
    # una cartola de cuenta y un estado de cuenta de tarjeta son documentos
    # distintos y se verifican distinto.
    es_tarjeta = True
    pistas = ()
    etiqueta = 'Estado de cuenta'

    def reconoce(self, texto):
        if not self.pistas:
            return False
        t = texto.lower()
        # El nombre de la casa comercial más la palabra que delata un estado
        # de cuenta: el nombre solo aparece también en una boleta.
        return any(p in t for p in self.pistas) and (
            'estado de cuenta' in t or 'facturado' in t or 'total a pagar' in t
        )

    def parsear(self, texto):
        fecha_fact = self._fecha_facturacion(texto)
        total = self._total(texto)

        movimientos, suma = [], Decimal(0)
        for linea in texto.splitlines():
            m = self._fila(linea.strip(), fecha_fact)
            if not m:
                continue
            movimientos.append(m)
            if 'no es un gasto' not in m.aviso.lower():
                suma += m.monto

        if len(movimientos) < 2:
            raise ErrorCartola(
                'No encontré el detalle de compras en este estado de cuenta. '
                'Tiene que ser el PDF que descargas de la tarjeta, no una foto '
                'ni una captura de pantalla.'
            )

        cartola = Cartola(
            banco=self.etiqueta,
            movimientos=movimientos,
            periodo=self._periodo(fecha_fact, movimientos),
            cuenta=self._contrato(texto),
            saldo_final=total,
        )
        self._verificar(cartola, suma, total)
        return cartola

    # -- la comprobación propia de este formato ----------------------

    def _verificar(self, cartola, suma, total):
        n = len(cartola.movimientos)
        if not total:
            cartola.cuadra = False
            cartola.descuadre = Decimal(0)
            cartola.nota_cuadre = (
                f'Leí {n} movimientos, pero este estado de cuenta no declara un '
                f'total contra el cual comprobarlos. Revísalos antes de guardar.'
            )
            return

        diferencia = abs(suma - total)
        cartola.descuadre = diferencia

        # Hasta un 1% se tolera: los estados arrastran ajustes de pesos del
        # período anterior que no salen como fila. Fallar por nueve pesos
        # sería un falso positivo todos los meses.
        margen = max(total / 100, Decimal(50))
        if diferencia <= margen:
            cartola.cuadra = True
            cartola.nota_cuadre = (
                f'Las {n} filas suman lo mismo que el total facturado que declara '
                f'el estado de cuenta, así que no falta ninguna compra.'
            )
            return

        # Más de un 15% no es un ajuste: es que el formato no era el
        # supuesto. Antes que entregar una lista inventada, no se entrega.
        if diferencia > total * Decimal('0.15'):
            raise ErrorCartola(
                'Encontré compras en este estado de cuenta, pero no suman el '
                'total facturado que él mismo declara: el formato necesita un '
                'lector propio. Mándame el PDF y lo agrego.'
            )

        cartola.cuadra = False
        cartola.nota_cuadre = (
            f'La suma de las filas se aleja en {diferencia:,.0f} del total facturado. '
            f'Falta o sobra alguna compra: revísalas una por una.'
        ).replace(',', '.')

    # -- extracción --------------------------------------------------

    def _fila(self, linea, fecha_fact):
        bajo = linea.lower()
        if not linea or any(p in bajo for p in NO_ES_FILA):
            return None

        fecha, fin = self._fecha_en(linea)
        if not fecha:
            return None

        resto = linea[fin:]
        cifras = list(CIFRA.finditer(resto))
        if not cifras:
            return None

        # La última cifra de la línea es lo que se cobra este mes.
        monto = abs(plata(cifras[-1].group(2)))
        if monto <= 0:
            return None

        desc = ' '.join(resto[:cifras[0].start()].split())[:200]
        if not desc:
            return None

        ca, ct = self._cuotas(resto)

        if any(p in desc.lower() for p in NO_ES_GASTO):
            return MovimientoLeido(
                fecha=fecha, descripcion=desc, monto=monto, tipo='EGRESO', saldo=0,
                aviso='No es un gasto: es un pago a la tarjeta. Ya lo tienes en '
                      'la cartola de tu cuenta corriente.',
            )

        if ct > 1:
            # La cuota es del mes que se factura, no del día de la compra.
            # La marca de cuál cuota es, además, hace que el mes siguiente
            # no se lea como la misma fila.
            return MovimientoLeido(
                fecha=fecha_fact or fecha,
                descripcion=f'{desc} · cuota {ca} de {ct}'[:200],
                monto=monto, tipo='EGRESO', saldo=0,
                cuota_actual=ca, cuota_total=ct,
                aviso=f'Compra del {fecha.strftime("%d/%m/%Y")} en {ct} cuotas. '
                      f'Se anota en este mes porque es la cuota que pagas ahora.',
            )

        return MovimientoLeido(
            fecha=fecha, descripcion=desc, monto=monto, tipo='EGRESO', saldo=0,
        )

    def _cuotas(self, resto):
        """La marca de cuotas, si la fila la trae y es creíble."""
        for m in CUOTA.finditer(resto):
            a, t = int(m.group(1)), int(m.group(2))
            if 1 <= a <= t <= 60 and t > 1:
                return a, t
        return 0, 0

    def _fecha_en(self, linea):
        m = FECHA_NUM.search(linea)
        if m:
            f = self._armar(*(int(x) for x in m.groups()))
            if f:
                return f, m.end()
        m = FECHA_LETRA.search(linea)
        if m:
            d, mes, a = m.groups()
            n = MES_LETRAS.get(mes[:3].lower())
            if n:
                f = self._armar(int(d), n, int(a))
                if f:
                    return f, m.end()
        return None, 0

    def _armar(self, d, mes, a):
        if a < 100:
            a += 2000
        try:
            return datetime(a, mes, d).date()
        except ValueError:
            try:
                return datetime(a, d, mes).date()
            except ValueError:
                return None

    # -- cabecera ----------------------------------------------------

    def _total(self, texto):
        m = TOTAL.search(texto)
        return plata(m.group(1)) if m else None

    def _fecha_facturacion(self, texto):
        for patron in (FECHA_FACT, VENCE):
            m = patron.search(texto)
            if not m:
                continue
            try:
                txt = m.group(1).replace('-', '/').replace('.', '/')
                d, mes, a = (int(x) for x in txt.split('/'))
                return self._armar(d, mes, a)
            except (ValueError, TypeError):
                continue
        return None

    def _contrato(self, texto):
        m = CONTRATO.search(texto)
        if not m:
            return ''
        num = re.sub(r'[^\dXx*]', '', m.group(1))
        return '…' + num[-4:] if len(num) > 4 else num

    def _periodo(self, fecha_fact, movimientos):
        f = fecha_fact or (movimientos[0].fecha if movimientos else None)
        return f'{MESES[f.month - 1]} {f.year}' if f else ''


# ---------------------------------------------------------------------
#  Ripley: la descripción va antes de la fecha
# ---------------------------------------------------------------------
#  El motor genérico se apoya en que la última cifra de la fila es el cargo
#  del mes. Ripley imprime una columna más a la derecha — el lugar de la
#  operación — y pone la descripción ANTES de la fecha, no después:
#
#     37/48  804.508  1.467.480  MUNICIPALIDAD PUCHUN  08/JUL/23  67.043  PUCHUNCAVI
#     41.560  CASA IDEAS MARINA AR COMPRA SIMPLE  01/AGO/26  41.560  VINA DEL MAR
#
#  Con la regla genérica la descripción queda vacía y la fila se descarta
#  entera: el estado de cuenta entraba sin ningún movimiento.
#
#  Y hay un segundo problema, peor: pypdf no deja separador entre columnas.
#  La fila de arriba llega así, todo pegado:
#
#     37/48804.5081.467.480MUNICIPALIDAD PUCHUN COMPRA EN CUOTA08/JUL/23 67.043PUCHUNCAVI
#
#  Así que no se puede partir la fila por espacios ni contar cifras. Quedan
#  dos anclas que el pegado no borra:
#
#    · LA FECHA DE OPERACIóN, «DD/MMM/AA» con el mes en letras y siempre
#      seguida de un espacio. Lo que viene inmediatamente después es el
#      cargo del mes; lo que sigue a eso es el lugar de la operación.
#    · LA PRIMERA LETRA DE LA FILA. Todo lo que hay antes son columnas
#      numéricas — cuota, monto de la operación, total, boleta — y desde
#      ahí empieza el nombre del comercio.
#
#  Comprobado contra los subtotales que el propio estado declara, las filas
#  suman exactamente los 410.724 de «2.1. TOTAL OPERACIONES».

# El mes en letras es lo único que distingue la fecha de operación de los
# números que la rodean cuando todo viene pegado. El espacio final también
# hace falta: sin él, «05/SEP/202683.580» de la cabecera se leería como fila.
FECHA_OP = re.compile(r'(\d{1,2})[/.-]([a-zA-Z]{3})[/.-](\d{2,4})(?=\s)')
FECHA_OP_NUM = re.compile(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})(?=\s)')

# El cargo del mes: la cifra pegada justo después de la fecha.
CARGO = re.compile(r'^\s*(-?\d[\d.]*)')

# Una comisión no trae fecha de operación porque no es una compra:
# «5.028COMISION MANT. 5.028». Cifra, texto que empieza en letra, cifra.
SIN_FECHA = re.compile(r'^(-?\d[\d.]*)([^\W\d_][^\d]*?)(-?\d[\d.]*)$')

# La marca de cuotas, al principio de la fila y pegada al monto: «37/48804.508».
CUOTA_INICIO = re.compile(r'^(\d{1,2})/(\d{1,2})')

FECHA_ESTADO = re.compile(
    r'fecha\s+estado\s+de\s+cuenta\s*:?\s*'
    r'(\d{1,2})[\s/.-]*([a-zA-Z]{3,10})\.?[\s/.-]*(\d{2,4})', re.I,
)

# «410.724(B)2.1. TOTAL OPERACIONES»: el estado declara un subtotal por
# sección, y la suma de los tres es contra lo que se comprueba.
SUBTOTAL = re.compile(r'(-?\d[\d.]*)\s*\(\s*([BCD])\s*\)')

# Al extraer el texto la cifra sale antes de su rótulo, así que se aceptan
# los dos órdenes.
FACTURADO = re.compile(
    r'(?:(-?\d[\d.]*)\s*monto\s+total\s+facturado'
    r'|monto\s+total\s+facturado[^\n\d]*\s*(-?\d[\d.]*))', re.I,
)

# Lo que viene después no se factura este mes: son compras del período
# siguiente, y contarlas las duplicaría al importar la cartola de agosto.
NO_FACTURADO = re.compile(r'2\.4\.|transacciones\s+no\s+facturadas', re.I)


@registrar('ripley', 'Tarjeta Ripley')
class LectorRipley(Retail):
    pistas = ('ripley',)
    etiqueta = 'Tarjeta Ripley'

    def parsear(self, texto):
        fecha_fact = self._fecha_estado(texto)
        movimientos, firmado = [], Decimal(0)

        for linea in texto.splitlines():
            if NO_FACTURADO.search(linea):
                break
            m = self._fila(linea.strip(), fecha_fact)
            if not m:
                continue
            movimientos.append(m)
            es_pago = 'no es un gasto' in m.aviso.lower()
            firmado += -m.monto if es_pago else m.monto

        if len(movimientos) < 2:
            raise ErrorCartola(
                'No encontré el detalle de compras en este estado de cuenta de '
                'Ripley. Tiene que ser el PDF que descargas de la tarjeta, no '
                'una foto ni una captura de pantalla.'
            )

        cartola = Cartola(
            banco=self.etiqueta,
            movimientos=movimientos,
            periodo=self._periodo(fecha_fact, movimientos),
            cuenta=self._contrato(texto),
            saldo_final=self._facturado(texto),
        )
        self._verificar_ripley(cartola, firmado, self._subtotales(texto))
        return cartola

    # -- la fila de Ripley -------------------------------------------

    def _fila(self, linea, fecha_fact):
        bajo = linea.lower()
        if not linea or any(p in bajo for p in NO_ES_FILA):
            return None

        ca, ct = 0, 0
        cm = CUOTA_INICIO.match(linea)
        if cm:
            a, t = int(cm.group(1)), int(cm.group(2))
            if 1 <= a <= t <= 60 and t > 1:
                ca, ct = a, t

        fecha, antes, despues = self._partir(linea)

        if fecha:
            post = CARGO.match(despues)
            if not post:
                return None
            monto = plata(post.group(1))
            desc = self._descripcion(antes)
        else:
            # «5.028COMISION MANT. 5.028»: las comisiones del mes no traen
            # fecha de operación porque no son una compra. Se fechan en el
            # día del estado de cuenta.
            sf = SIN_FECHA.match(linea)
            if not (sf and fecha_fact):
                return None
            fecha = fecha_fact
            monto = plata(sf.group(3))
            desc = sf.group(2)

        desc = ' '.join(desc.split())[:200]
        # Tres letras, no tres caracteres: los rótulos de sección del estado
        # — «9.571 (C) 2.2. PRODUCTOS…» — tienen la misma forma que una fila
        # y dejan un «(C)» donde debería ir el nombre del comercio.
        if monto == 0 or len(re.findall(r'[^\W\d_]', desc)) < 3:
            return None

        # El pago del mes anterior viene con signo negativo. No es un gasto:
        # es plata que salió de la cuenta corriente, donde ya está anotada.
        if monto < 0 or any(p in desc.lower() for p in NO_ES_GASTO):
            return MovimientoLeido(
                fecha=fecha, descripcion=desc, monto=abs(monto),
                tipo='EGRESO', saldo=0,
                aviso='No es un gasto: es un pago a la tarjeta. Ya lo tienes en '
                      'la cartola de tu cuenta corriente.',
            )

        if ct > 1:
            return MovimientoLeido(
                fecha=fecha_fact or fecha,
                descripcion=f'{desc} · cuota {ca} de {ct}'[:200],
                monto=monto, tipo='EGRESO', saldo=0,
                cuota_actual=ca, cuota_total=ct,
                aviso=f'Compra del {fecha.strftime("%d/%m/%Y")} en {ct} cuotas. '
                      f'Se anota en este mes porque es la cuota que pagas ahora.',
            )

        return MovimientoLeido(
            fecha=fecha, descripcion=desc, monto=monto, tipo='EGRESO', saldo=0,
        )

    def _descripcion(self, antes):
        """El nombre del comercio: desde la primera letra de la fila.

        Todo lo que hay a la izquierda son columnas numéricas. Cortar por la
        última cifra no sirve — hay comercios con número en el nombre, y
        productos también: «SB 708 COMPRA SIMPLE» quedaba en «COMPRA SIMPLE»
        y «…POLERA I YF OLD OG F45067» se comía el nombre entero.
        """
        m = re.search(r'[^\W\d_]', antes)
        return antes[m.start():] if m else ''

    def _partir(self, linea):
        """Corta la fila en la fecha de operación: (fecha, antes, después)."""
        m = FECHA_OP.search(linea)
        if m:
            d, mes, a = m.groups()
            n = MES_LETRAS.get(mes.lower())
            fecha = self._armar(int(d), n, int(a)) if n else None
        else:
            m = FECHA_OP_NUM.search(linea)
            fecha = self._armar(*(int(x) for x in m.groups())) if m else None
        if not (m and fecha):
            return None, '', ''
        return fecha, linea[:m.start()], linea[m.end():]

    # -- cabecera y comprobación -------------------------------------

    def _fecha_estado(self, texto):
        m = FECHA_ESTADO.search(texto)
        if not m:
            return super()._fecha_facturacion(texto)
        d, mes, a = m.groups()
        n = MES_LETRAS.get(mes[:3].lower())
        return self._armar(int(d), n, int(a)) if n else None

    def _facturado(self, texto):
        m = FACTURADO.search(texto)
        return plata(m.group(1) or m.group(2)) if m else None

    def _subtotales(self, texto):
        encontrados = {s: plata(c) for c, s in SUBTOTAL.findall(texto)}
        return sum(encontrados.values()) if encontrados else None

    def _verificar_ripley(self, cartola, firmado, esperado):
        n = len(cartola.movimientos)
        if esperado is None:
            return super()._verificar(cartola, cartola.egresos, cartola.saldo_final)

        diferencia = abs(firmado - esperado)
        cartola.descuadre = diferencia
        margen = max(abs(esperado) / 100, Decimal(50))

        if diferencia <= margen:
            cartola.cuadra = True
            cartola.nota_cuadre = (
                f'Las {n} filas suman lo mismo que los subtotales que declara el '
                f'estado de cuenta, así que no falta ninguna compra.'
            )
            return

        if diferencia > abs(esperado) * Decimal('0.15'):
            raise ErrorCartola(
                'Leí el detalle de este estado de cuenta Ripley, pero no suma los '
                'subtotales que él mismo declara. Mándame el PDF y reviso el formato.'
            )

        cartola.cuadra = False
        cartola.nota_cuadre = (
            f'La suma de las filas se aleja en {diferencia:,.0f} de los subtotales '
            f'del estado de cuenta. Revísalas una por una.'
        ).replace(',', '.')


# ---------------------------------------------------------------------
#  Los emisores de tarjeta de casa comercial en Chile
# ---------------------------------------------------------------------
#  Igual que con los bancos: el motor es uno solo y cada emisor aporta las
#  palabras que delatan su PDF. Agregar una casa comercial nueva es agregar
#  una línea.
#
#  CMR no está acá: tiene parser propio (cmr.py), con la columna de cuotas
#  y el titular/adicional en posiciones fijas.

EMISORES = (
    # Sin «jumbo» ni «paris» a secas: son nombres de comercio que aparecen en
    # el detalle de cualquier tarjeta, y hacían que un estado de Ripley con
    # una compra en Jumbo se leyera como si fuera de Cencosud.
    ('cencosud',  'Tarjeta Cencosud (Paris · Jumbo · Easy)',
     ('cencosud', 'tarjeta cencosud', 'paris.cl')),
    ('la_polar',  'Tarjeta La Polar',      ('la polar', 'lapolar')),
    ('abcdin',    'Tarjeta ABCDIN',        ('abcdin', 'abc din', 'dincard')),
    ('hites',     'Tarjeta Hites',         ('hites',)),
    ('tricot',    'Tarjeta Tricot',        ('tricot',)),
    ('corona',    'Tarjeta Corona',        ('corona',)),
    ('dijon',     'Tarjeta Dijon',         ('dijon',)),
    ('johnson',   'Tarjeta Johnson',       ('johnson',)),
    ('lider',     'Tarjeta Líder / BancoEstado', ('líder', 'lider', 'walmart')),
    ('unimarc',   'Tarjeta Unimarc',       ('unimarc',)),
    ('entel',     'Cuenta Entel',          ('entel',)),
    ('retail',    'Otra tarjeta de casa comercial', ()),
)


def _registrar_emisores():
    for clave, nombre, pistas in EMISORES:
        cls = type(
            'Lector' + clave.title().replace('_', ''),
            (Retail,),
            {'pistas': pistas,
             'etiqueta': nombre if pistas else 'Estado de cuenta de tarjeta'},
        )
        registrar(clave, nombre)(cls)


_registrar_emisores()
