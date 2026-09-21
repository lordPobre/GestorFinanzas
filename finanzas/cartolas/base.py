"""El motor: texto del PDF adentro, movimientos con signo afuera.

EL PROBLEMA Y SU SOLUCIÓN
-------------------------
Una cartola imprime tres columnas de plata — Cargo, Abono y Saldo — pero al
extraer el texto del PDF las columnas vacías desaparecen. De una fila solo
sobreviven dos montos:

    31/08/2026 CASA MATRIZ PAC Ahorro $ 10.000 $ 703.551

¿Los diez mil salieron o entraron? El texto no lo dice. El saldo sí: viene
corrido, fila a fila. Restando el saldo de una fila con el de la siguiente
(que es el movimiento anterior, porque la cartola va del más nuevo al más
viejo) sale la diferencia exacta, y su signo es la respuesta.

    703.551 - 713.551 = -10.000  ->  cargo de 10.000

No es una estimación: el monto de la resta tiene que coincidir con el monto
impreso en la fila. Si no coincide, la fila se leyó mal y se marca, en vez
de entrar a la base con el signo equivocado.

Y como el saldo es una cadena, se verifica entera de punta a punta: el saldo
después del movimiento más viejo tiene que dar el Saldo Inicial, y el del más
nuevo el Saldo Contable. Si la cadena no cierra, el archivo no se importa.
Es la diferencia entre un parser que se equivoca en silencio y uno que avisa.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class ErrorCartola(Exception):
    """El archivo no se pudo leer. El mensaje va directo al usuario."""


# Topes de lectura. Un PDF de 6 MB —lo que deja pasar la vista— puede traer
# miles de páginas comprimidas: extraer su texto se come la memoria del
# proceso y tumba la app para todos, no solo para quien lo subió. Los límites
# están muy por encima de cualquier cartola real: un estado de cuenta de
# tarjeta anda en 2 a 20 páginas y unos cientos de movimientos.
MAX_PAGINAS = 80
MAX_CARACTERES = 1_500_000
MAX_MOVIMIENTOS = 2_000

MUESTRA_LINEAS = 45

ESTRUCTURA = frozenset('''
fecha fechas hora saldo saldos anterior final inicial contable disponible
total totales cargo cargos abono abonos giro giros deposito depositos
depósito depósitos movimiento movimientos detalle descripcion descripción
operacion operación cartola cuentarut cuenta cuentas corriente vista ahorro
rut cliente nombre titular banco bancoestado santander bci scotiabank itau
itaú falabella chile security bice consorcio internacional coopeuch btg
tenpo mach mercado pago global chek heroes héroes ripley cencosud paris
jumbo easy polar hites abcdin tricot corona dijon johnson lider líder
unimarc entel cmr tarjeta estado tarjetas monto montos valor valores
cuota cuotas compra compras tef pac pat transferencia transf efectivo caja
vecina webpay sucursal internet oficina casa matriz periodo período desde
hasta emision emisión pagina página interes intereses comision comisión
iva seleccionada resumen utilizado facturado avance credito crédito debito
débito linea línea numero número nro num doc documento referencia glosa
concepto comercio pesos moneda nacional
ene feb mar abr may jun jul ago sep oct nov dic
enero febrero marzo abril mayo junio julio agosto septiembre octubre
noviembre diciembre
'''.split())


def muestra_anonima(texto, lineas=MUESTRA_LINEAS):
    """El texto extraído con la forma intacta y los datos borrados.

    Sirve para agregar un formato nuevo sin que nadie mande su cartola: los
    dígitos pasan a 9 y las palabras que no son de la estructura del
    documento a X, así que quedan las etiquetas, el orden de las columnas y
    la forma de las fechas y los montos, y no queda ningún dato personal.
    """
    utiles = [l.rstrip() for l in (texto or '').splitlines() if l.strip()]
    return '\n'.join(_enmascarar(l) for l in utiles[:lineas])


def _enmascarar(linea):
    def palabra(m):
        w = m.group(0)
        return w if w.lower() in ESTRUCTURA else 'X' * len(w)
    return re.sub(r'[^\W\d_]{3,}', palabra, re.sub(r'\d', '9', linea))


@dataclass
class MovimientoLeido:
    fecha: date
    descripcion: str
    monto: Decimal
    tipo: str                    # 'INGRESO' | 'EGRESO'
    saldo: Decimal
    # Lo que rellena analisis.py
    categoria: str = 'Otros'
    cuota_actual: int = 0
    cuota_total: int = 0
    es_suscripcion: bool = False
    ya_existe: bool = False
    aviso: str = ''

    @property
    def es_cuota(self):
        return self.cuota_total > 1


@dataclass
class Cartola:
    banco: str
    movimientos: list = field(default_factory=list)
    periodo: str = ''
    cuenta: str = ''
    saldo_inicial: Decimal = None
    saldo_final: Decimal = None
    cuadra: bool = True
    descuadre: Decimal = Decimal(0)
    # Cada formato se verifica distinto — una cuenta corriente por la cadena
    # de saldos, una tarjeta por la suma de las cuotas contra el total
    # facturado — así que el texto lo escribe el parser, no la plantilla.
    nota_cuadre: str = ''

    @property
    def ingresos(self):
        return sum((m.monto for m in self.movimientos if m.tipo == 'INGRESO'), Decimal(0))

    @property
    def egresos(self):
        return sum((m.monto for m in self.movimientos if m.tipo == 'EGRESO'), Decimal(0))


# ---------------------------------------------------------------------
#  Utilidades compartidas entre bancos
# ---------------------------------------------------------------------

def plata(txt):
    """'$ 1.234.567' -> Decimal('1234567').

    En Chile el punto separa miles y no decimales, así que se borra: leerlo
    como decimal convertiría un millón doscientos en un uno coma dos.
    """
    limpio = re.sub(r'[^\d,-]', '', txt or '').replace(',', '.')
    return Decimal(limpio or 0)


def texto_de_pdf(binario):
    """Saca el texto del PDF.

    pypdf y no pdfplumber: es Python puro, pesa poco más de un mega y no
    arrastra Pillow ni pdfminer. En una cuenta gratuita de PythonAnywhere,
    donde el disco es de 512 MB y no se pueden instalar binarios del
    sistema, esa diferencia decide si la función existe o no.

    Tampoco hace falta nada más pesado: el signo sale del saldo corrido, no
    de la posición de las columnas, así que el texto plano alcanza.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ErrorCartola(
            'Falta la librería para leer PDF. Instálala con: pip install --user pypdf'
        )

    try:
        lector = PdfReader(binario)
        if lector.is_encrypted:
            # Las cartolas suelen venir con clave: el RUT sin dígito verificador.
            raise ErrorCartola('El PDF está protegido con clave. Guárdalo sin clave y vuelve a subirlo.')

        paginas = len(lector.pages)
        if paginas > MAX_PAGINAS:
            raise ErrorCartola(
                f'El PDF tiene {paginas} páginas y el tope son {MAX_PAGINAS}. '
                'Si es una cartola de varios años, súbela por partes.')

        # Se corta al ir acumulando, no después: si el texto ya se extrajo
        # completo, la memoria ya se gastó y el límite llegó tarde.
        piezas, largo = [], 0
        for pagina in lector.pages:
            trozo = pagina.extract_text() or ''
            largo += len(trozo)
            if largo > MAX_CARACTERES:
                raise ErrorCartola(
                    'El PDF trae demasiado texto para procesarlo de una. '
                    'Súbelo por partes, o revisa que sea una cartola y no otro documento.')
            piezas.append(trozo)
        return '\n'.join(piezas)
    except ErrorCartola:
        raise
    except Exception:
        raise ErrorCartola('No se pudo abrir el PDF. ¿Seguro que es la cartola?')


def resolver_signos(filas, saldo_inicial):
    """El corazón: convierte (monto, saldo) en (monto, tipo) usando la cadena.

    'filas' viene en el orden en que la cartola las imprime, del movimiento
    más nuevo al más viejo. Devuelve (movimientos, descuadre_total).
    """
    movimientos, descuadre = [], Decimal(0)

    for i, f in enumerate(filas):
        # El saldo que había ANTES de este movimiento es el de la fila
        # siguiente, que es la anterior en el tiempo. Para la última fila —
        # la más vieja — ese saldo es el Saldo Inicial de la cartola.
        saldo_previo = filas[i + 1]['saldo'] if i + 1 < len(filas) else saldo_inicial
        if saldo_previo is None:
            # Sin punto de apoyo no se puede decidir. Antes que adivinar, se
            # entrega como egreso y se avisa: el usuario lo corrige en la
            # pantalla de revisión.
            movimientos.append(MovimientoLeido(
                fecha=f['fecha'], descripcion=f['descripcion'], monto=f['monto'],
                tipo='EGRESO', saldo=f['saldo'],
                aviso='No se pudo determinar si entró o salió. Revísalo.',
            ))
            continue

        delta = f['saldo'] - saldo_previo
        tipo = 'INGRESO' if delta > 0 else 'EGRESO'

        aviso = ''
        if abs(delta) != f['monto']:
            # La resta de saldos no da el monto impreso: la fila se leyó mal,
            # o la cartola trae una fila que no altera el saldo. Se deja
            # pasar marcada, nunca en silencio.
            diff = abs(abs(delta) - f['monto'])
            descuadre += diff
            aviso = 'El saldo no calza con el monto de esta fila. Revísala.'

        movimientos.append(MovimientoLeido(
            fecha=f['fecha'], descripcion=f['descripcion'], monto=f['monto'],
            tipo=tipo, saldo=f['saldo'], aviso=aviso,
        ))

    return movimientos, descuadre


# ---------------------------------------------------------------------
#  Registro de bancos
# ---------------------------------------------------------------------

BANCOS = {}


def registrar(clave, nombre):
    def deco(cls):
        cls.clave, cls.nombre = clave, nombre
        BANCOS[clave] = cls
        return cls
    return deco


def _topar(cartola):
    """Se niega a entregar una cartola con más movimientos de los razonables.

    Cortar la lista a los primeros 2.000 sería peor que fallar: la pantalla de
    revisión mostraría una cartola aparentemente completa y el resto
    desaparecería sin que nadie lo note. Y los movimientos viajan en la
    sesión hasta que se confirman, así que un archivo enorme también infla
    cada peticion de esa persona.
    """
    cantidad = len(cartola.movimientos)
    if cantidad > MAX_MOVIMIENTOS:
        raise ErrorCartola(
            f'La cartola trae {cantidad} movimientos y el tope son '
            f'{MAX_MOVIMIENTOS}. Súbela por periodos más cortos.')
    return cartola


def leer_cartola(binario, banco='', nombre=''):
    """Punto de entrada. Con banco='' prueba a reconocerlo solo."""
    from .tabla import es_tabla, leer_tabla

    if es_tabla(nombre):
        return _topar(leer_tabla(binario, nombre))

    texto = texto_de_pdf(binario)
    try:
        return _leer(texto, banco)
    except ErrorCartola as e:
        if not getattr(e, 'muestra', ''):
            e.muestra = muestra_anonima(texto)
        raise


def _leer(texto, banco=''):
    if banco:
        parser = BANCOS.get(banco)
        if not parser:
            raise ErrorCartola('Ese banco todavía no está soportado.')
        return _topar(parser().parsear(texto))

    for parser in BANCOS.values():
        if parser().reconoce(texto):
            return _topar(parser().parsear(texto))

    # Ninguno lo reconoció. Quedan los dos motores genéricos, y se prueban en
    # ese orden porque comprueban cosas distintas:
    #
    #   · el de cartola busca la forma "fecha descripción monto saldo" y
    #     verifica la cadena de saldos;
    #   · el de tarjeta busca el detalle de compras y verifica la suma contra
    #     el total facturado.
    #
    # Ninguno adivina a ciegas: los dos se niegan si su comprobación no cierra,
    # así que intentarlo no puede ensuciar la base. Si los dos fallan se
    # devuelve el error del primero, que es el caso más común.
    primero = None
    for clave in ('generico', 'retail'):
        lector = BANCOS.get(clave)
        if not lector:
            continue
        try:
            leida = lector().parsear(texto)
        except ErrorCartola as e:
            primero = primero or e
            continue
        # El tope va fuera del try: si se aplicara dentro, su error se
        # confundiría con «este lector no la reconoció» y el usuario vería
        # un mensaje sobre el formato en vez del tamaño.
        return _topar(leida)

    if primero:
        raise primero
    raise ErrorCartola('No reconocí el formato de esta cartola.')
