import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from io import BytesIO


class ErrorCartola(Exception):
    pass


class ClaveCartola(ErrorCartola):
    def __init__(self, incorrecta=False):
        self.incorrecta = incorrecta
        super().__init__('Esa clave no abre el PDF. Revísala y vuelve a intentarlo.' if incorrecta
                         else 'Este PDF está protegido con clave. Escríbela para abrirlo.')


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
    tipo: str
    saldo: Decimal
    categoria: str = 'Otros'
    cuota_actual: int = 0
    cuota_total: int = 0
    es_suscripcion: bool = False
    ya_existe: bool = False
    aviso: str = ''
    fecha_compra: date = None
    mover_id: int = None
    reemplaza_id: int = None
    reemplaza_seguro: bool = False
    reemplaza_desc: str = ''
    reemplaza_fecha: str = ''
    deuda_id: int = None
    deuda_periodo: int = None
    deuda_texto: str = ''
    prestamo_id: int = None
    prestamo_texto: str = ''
    vinculo_seguro: bool = False

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
    nota_cuadre: str = ''

    @property
    def ingresos(self):
        return sum((m.monto for m in self.movimientos if m.tipo == 'INGRESO'), Decimal(0))

    @property
    def egresos(self):
        return sum((m.monto for m in self.movimientos if m.tipo == 'EGRESO'), Decimal(0))


def plata(txt):
    limpio = re.sub(r'[^\d,-]', '', txt or '').replace(',', '.')
    return Decimal(limpio or 0)


def texto_de_pdf(binario):
    return '\n'.join(paginas_de_pdf(binario))


def _descifrar(lector, clave):
    from pypdf.errors import DependencyError
    try:
        for intento in ([clave] if clave else []) + ['']:
            if lector.decrypt(intento):
                return True
    except DependencyError as e:
        raise ErrorCartola(
            'Falta la librería para abrir PDF con clave. Instálala con: pip install --user cryptography'
        ) from e
    return False


def abrir_pdf(contenido, clave=''):
    if b'%PDF' not in contenido[:1024]:
        return contenido
    try:
        from pypdf import PdfReader, PdfWriter
        lector = PdfReader(BytesIO(contenido))
        if not lector.is_encrypted:
            return contenido
    except Exception:
        return contenido

    if not _descifrar(lector, clave):
        raise ClaveCartola(incorrecta=bool(clave))

    try:
        escritor = PdfWriter()
        for pagina in lector.pages:
            escritor.add_page(pagina)
        salida = BytesIO()
        escritor.write(salida)
    except Exception as e:
        raise ErrorCartola('No se pudo abrir el PDF. ¿Seguro que es la cartola?') from e
    return salida.getvalue()


def paginas_de_pdf(binario):
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ErrorCartola(
            'Falta la librería para leer PDF. Instálala con: pip install --user pypdf'
        ) from e

    try:
        lector = PdfReader(binario)
        if lector.is_encrypted and not _descifrar(lector, ''):
            raise ClaveCartola()

        paginas = len(lector.pages)
        if paginas > MAX_PAGINAS:
            raise ErrorCartola(
                f'El PDF tiene {paginas} páginas y el tope son {MAX_PAGINAS}. '
                'Si es una cartola de varios años, súbela por partes.')

        piezas, largo = [], 0
        for pagina in lector.pages:
            trozo = pagina.extract_text() or ''
            largo += len(trozo)
            if largo > MAX_CARACTERES:
                raise ErrorCartola(
                    'El PDF trae demasiado texto para procesarlo de una. '
                    'Súbelo por partes, o revisa que sea una cartola y no otro documento.')
            piezas.append(trozo)
        return piezas
    except ErrorCartola:
        raise
    except Exception as e:
        raise ErrorCartola('No se pudo abrir el PDF. ¿Seguro que es la cartola?') from e


def resolver_signos(filas, saldo_inicial):
    movimientos, descuadre = [], Decimal(0)

    for i, f in enumerate(filas):
        saldo_previo = filas[i + 1]['saldo'] if i + 1 < len(filas) else saldo_inicial
        if saldo_previo is None:
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
            diff = abs(abs(delta) - f['monto'])
            descuadre += diff
            aviso = 'El saldo no calza con el monto de esta fila. Revísala.'

        movimientos.append(MovimientoLeido(
            fecha=f['fecha'], descripcion=f['descripcion'], monto=f['monto'],
            tipo=tipo, saldo=f['saldo'], aviso=aviso,
        ))

    return movimientos, descuadre


BANCOS = {}


def registrar(clave, nombre):
    def deco(cls):
        cls.clave, cls.nombre = clave, nombre
        BANCOS[clave] = cls
        return cls
    return deco


def _topar(cartola):
    cantidad = len(cartola.movimientos)
    if cantidad > MAX_MOVIMIENTOS:
        raise ErrorCartola(
            f'La cartola trae {cantidad} movimientos y el tope son '
            f'{MAX_MOVIMIENTOS}. Súbela por periodos más cortos.')
    return cartola


FOTO_SIN_IA = ('Las fotos y los PDF escaneados se leen con IA, y ahora no está disponible. '
               'Sube el PDF o el Excel que descarga el banco.')


def leer_cartola(binario, banco='', nombre='', usuario=None):
    contenido = binario.getvalue() if hasattr(binario, 'getvalue') else binario.read()

    def respaldo():
        return _leer_clasico(BytesIO(contenido), banco, nombre)

    if usuario is None:
        return respaldo()
    from .lector_ia import leer_con_ia
    return _topar(leer_con_ia(contenido, nombre, banco, usuario, respaldo))


def _leer_clasico(binario, banco, nombre):
    from .lector_ia import es_imagen
    from .tabla import es_tabla, leer_tabla

    if es_tabla(nombre):
        return _topar(leer_tabla(binario, nombre))
    if es_imagen(binario.getvalue()[:16]):
        raise ErrorCartola(FOTO_SIN_IA)

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
        try:
            leida = parser().parsear(texto)
        except ErrorCartola as elegido:
            try:
                return _leer(texto)
            except ErrorCartola:
                raise elegido from None
        return _topar(leida)

    for parser in BANCOS.values():
        if parser().reconoce(texto):
            return _topar(parser().parsear(texto))

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
        return _topar(leida)

    if primero:
        raise primero
    raise ErrorCartola('No reconocí el formato de esta cartola.')
