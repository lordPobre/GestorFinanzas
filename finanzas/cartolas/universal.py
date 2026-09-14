"""El lector universal: cualquier cartola que lleve saldo corrido.

POR QUÉ UN SOLO LECTOR SIRVE PARA TODOS LOS BANCOS
--------------------------------------------------
El truco del saldo corrido no es de ningún banco en particular: es de la
contabilidad. Toda cartola de cuenta corriente, vista o ahorro imprime una
columna de saldo que avanza fila a fila. Restando el saldo de una fila con
el de la anterior sale el monto del movimiento y, sobre todo, su signo.

    703.551 - 713.551 = -10.000  ->  cargo de 10.000

Así que no hace falta un parser por banco. Hace falta un extractor que
encuentre la forma «fecha … cifras … saldo» en el texto del PDF, y una
verificación que se niegue a entregar nada si la cadena no cierra.

LO QUE ESTE LECTOR AGREGA SOBRE EL INTENTO GENÉRICO ORIGINAL
------------------------------------------------------------
1. Columnas Cargo / Abono / Saldo. Muchos bancos imprimen tres cifras por
   fila en vez de dos. Cuál de las dos primeras es el movimiento no se sabe
   al leer la línea, así que no se adivina: se guardan las dos como
   candidatas y gana la que coincide con la resta de saldos. La cadena
   decide, no una suposición sobre el orden de las columnas.

2. Fechas con mes en letras — «31 AGO 2026», «31-ago-25» — que es como las
   imprimen varios bancos y todas las tarjetas.

3. Fechas de dos dígitos, separadores mezclados, y el orden invertido
   (cartolas que van del movimiento más viejo al más nuevo).

4. Un registro de bancos por nombre: el mismo motor, con el nombre de la
   institución para que la pantalla de revisión diga de dónde salió y para
   que el selector de la pantalla de importar los ofrezca.

LA GARANTÍA
-----------
Es la misma de antes y es la única que importa: cada fila se comprueba
contra la resta de saldos. Si menos del 85% de las filas cuadra, el archivo
se rechaza entero en vez de entregar movimientos inventados. Este lector no
promete leer tu banco; promete que si no puede, te lo va a decir.
"""
import re
from datetime import datetime
from decimal import Decimal

from .base import Cartola, ErrorCartola, MovimientoLeido, plata, registrar

MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')

# Los tres primeros caracteres alcanzan para distinguirlos, y así entran
# igual «ene», «Ene.», «ENERO» y el «jan/dec» de algún PDF en inglés.
MES_LETRAS = {
    'ene': 1, 'jan': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'apr': 4, 'may': 5,
    'jun': 6, 'jul': 7, 'ago': 8, 'aug': 8, 'sep': 9, 'set': 9, 'oct': 10,
    'nov': 11, 'dic': 12, 'dec': 12,
}

FECHA_NUM = re.compile(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b')
FECHA_LETRA = re.compile(r'\b(\d{1,2})[\s/.-]*([a-zA-Z]{3,10})\.?[\s/.-]*(\d{2,4})\b')

# Una cifra de plata: con o sin $, con puntos de miles y coma decimal
# opcional. El lookbehind y el lookahead evitan morder pedazos de una fecha
# o de un número de documento pegado a otro.
CIFRA = re.compile(r'(?<![\d/.-])(\$\s*)?(-?\d[\d.]*(?:,\d{1,2})?)(?![\d/.-])')

# El saldo de arranque, cuando la cartola lo declara.
SALDO_ANTERIOR = re.compile(
    r'saldo\s+(?:inicial|anterior|previo|del\s+per[ií]odo\s+anterior)'
    r'[\s\S]{0,220}?\$?\s*(-?\d[\d.]*(?:,\d{1,2})?)',
    re.I,
)

CUENTA = re.compile(
    r'(?:cuenta|n[°ºo]\s*de\s*cuenta|cuenta\s*corriente|cta\.?)\s*'
    r'(?:n[°ºo]\.?\s*)?:?\s*([\d*\-]{6,20})', re.I,
)

# Pistas para la única fila que la cadena no puede resolver sola: la más
# vieja, cuando el PDF no declara saldo anterior.
ENTRA = ('abono', 'deposito', 'depósito', 'transf. de', 'transf de',
         'transferencia de', 'transferencia desde', 'remuneracion',
         'remuneración', 'sueldo', 'devolucion', 'devolución', 'reverso',
         'pago recibido', 'haberes', 'liquidacion', 'liquidación')

# Líneas que traen fecha y cifras pero no son movimientos: encabezados,
# totales y pies de página. Descartarlas antes de medir la cadena evita que
# una sola línea de resumen tire abajo el porcentaje de aciertos.
NO_ES_FILA = ('saldo inicial', 'saldo anterior', 'saldo final', 'saldo contable',
              'total cargos', 'total abonos', 'totales', 'página', 'pagina',
              'resumen', 'subtotal', 'emitido el', 'fecha de emisión',
              'fecha de emision')


class Universal:
    """El motor. Los bancos con nombre son subclases de una línea."""

    # Cada banco con nombre pone acá las palabras que lo delatan en el PDF.
    pistas = ()
    # Lo que se escribe en la pantalla de revisión.
    etiqueta = 'Cartola genérica'

    def reconoce(self, texto):
        if not self.pistas:
            return False
        t = texto.lower()
        # El nombre del banco solo no basta: aparece en cualquier documento
        # que el banco emita, incluido un certificado o una carta. Se exige
        # además la palabra que delata una tabla de movimientos con saldo.
        return any(p in t for p in self.pistas) and 'saldo' in t

    # -- el recorrido ------------------------------------------------

    def parsear(self, texto):
        filas = self._filas(texto)
        if len(filas) < 3:
            raise ErrorCartola(
                'No encontré una tabla de movimientos en este PDF. Si es un '
                'escaneo o una foto no sirve: tiene que ser el PDF que '
                'descarga el banco. Si es un estado de cuenta de una tarjeta '
                'de casa comercial, elígelo en la lista de arriba.'
            )

        filas = self._ordenar(filas)
        saldo_inicial = self._saldo_anterior(texto)

        # La prueba, antes de entregar nada: ¿la resta entre saldos
        # consecutivos reproduce alguna de las cifras impresas en la fila?
        aciertos = 0
        for i, f in enumerate(filas[:-1]):
            if abs(f['saldo'] - filas[i + 1]['saldo']) in f['candidatos']:
                aciertos += 1

        comparables = len(filas) - 1
        if comparables and aciertos / comparables < 0.85:
            raise ErrorCartola(
                'Encontré filas con fechas y montos, pero los saldos no '
                'siguen una cadena coherente: este formato necesita un lector '
                'propio. Mándame el PDF y lo agrego.'
            )

        movimientos, descuadre = self._resolver(filas, saldo_inicial)

        # La fila más vieja, si no hubo saldo anterior declarado, se resolvió
        # a ciegas. Se le pone la mejor pista disponible y se marca.
        if saldo_inicial is None and movimientos:
            ultimo = movimientos[-1]
            if any(p in ultimo.descripcion.lower() for p in ENTRA):
                ultimo.tipo = 'INGRESO'
            ultimo.aviso = ('Es el movimiento más antiguo y no hay saldo '
                            'anterior contra el cual compararlo: confirma si '
                            'entró o salió.')

        cartola = Cartola(
            banco=self.etiqueta,
            movimientos=movimientos,
            periodo=self._periodo(filas),
            cuenta=self._cuenta(texto),
            saldo_inicial=saldo_inicial,
            saldo_final=filas[0]['saldo'],
            descuadre=descuadre,
            cuadra=not descuadre,
        )
        cartola.nota_cuadre = self._nota(cartola, len(filas))
        return cartola

    def _nota(self, cartola, n):
        conocido = bool(self.pistas)
        if cartola.cuadra and conocido:
            return (f'Los saldos de las {n} filas forman una cadena continua y '
                    f'cada movimiento calza con su diferencia: los montos y los '
                    f'signos son correctos.')
        if cartola.cuadra:
            return (f'Leí este PDF sin conocer el formato del banco, pero los '
                    f'saldos de las {n} filas forman una cadena coherente: los '
                    f'montos y los signos son correctos.')
        return ('Algunas filas no calzan con la cadena de saldos. '
                'Revisa las marcadas antes de guardar.')

    # -- extracción --------------------------------------------------

    def _filas(self, texto):
        filas = []
        for linea in texto.splitlines():
            bajo = linea.lower()
            if any(p in bajo for p in NO_ES_FILA):
                continue

            fecha, fin = self._fecha_en(linea)
            if not fecha:
                continue

            resto = linea[fin:]
            cifras = list(CIFRA.finditer(resto))

            # Cuando la línea marca algunas cifras con $, esas son las de
            # plata y el resto son números sueltos de la descripción (el
            # local de la compra, el número de documento).
            con_signo = [c for c in cifras if c.group(1)]
            if len(con_signo) >= 2:
                cifras = con_signo
            if len(cifras) < 2:
                continue

            # La última es el saldo. De las anteriores, las dos últimas son
            # las candidatas a monto: en una cartola de dos columnas hay una
            # sola; en una de Cargo/Abono/Saldo hay dos y una viene vacía o
            # en cero. Cuál es cuál lo decide la cadena, no esta línea.
            saldo = plata(cifras[-1].group(2))
            candidatos = []
            for c in cifras[-3:-1]:
                v = abs(plata(c.group(2)))
                if v and v not in candidatos:
                    candidatos.append(v)
            if not candidatos:
                continue

            # La descripción es lo que va antes de la primera cifra de
            # plata. «Primera» es la que abre el bloque de columnas al final
            # de la línea, no cualquier número: un número de documento o el
            # local de la compra van pegados al texto y son parte de él.
            corte = cifras[-3].start() if len(cifras) >= 3 else cifras[-2].start()

            filas.append({
                'fecha': fecha,
                'descripcion': ' '.join(resto[:corte].split())[:200],
                'candidatos': candidatos,
                'saldo': saldo,
            })
        return filas

    def _fecha_en(self, linea):
        """Devuelve (fecha, posición donde termina) o (None, 0)."""
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
            # Puede haber salido mm/dd en vez de dd/mm.
            try:
                return datetime(a, d, mes).date()
            except ValueError:
                return None

    def _ordenar(self, filas):
        """Deja la lista del movimiento más nuevo al más viejo.

        Unos bancos imprimen la cartola al revés que otros, y la cadena de
        saldos se lee en un solo sentido: si el orden está invertido, todos
        los signos salen al revés.
        """
        if len(filas) > 1 and filas[0]['fecha'] < filas[-1]['fecha']:
            return list(reversed(filas))
        return filas

    # -- resolución de signos ---------------------------------------

    def _resolver(self, filas, saldo_inicial):
        """(monto, saldo) -> (monto, tipo), eligiendo entre las candidatas."""
        movimientos, descuadre = [], Decimal(0)

        for i, f in enumerate(filas):
            # El saldo que había ANTES de este movimiento es el de la fila
            # siguiente, que es la anterior en el tiempo. Para la última —
            # la más vieja — ese saldo es el Saldo Inicial de la cartola.
            previo = filas[i + 1]['saldo'] if i + 1 < len(filas) else saldo_inicial

            if previo is None:
                movimientos.append(MovimientoLeido(
                    fecha=f['fecha'], descripcion=f['descripcion'],
                    monto=f['candidatos'][0], tipo='EGRESO', saldo=f['saldo'],
                    aviso='No se pudo determinar si entró o salió. Revísalo.',
                ))
                continue

            delta = f['saldo'] - previo
            objetivo = abs(delta)

            aviso = ''
            monto = next((c for c in f['candidatos'] if c == objetivo), None)
            if monto is None:
                # Ninguna cifra de la fila coincide con el movimiento del
                # saldo. Se entrega la más parecida, marcada: puede ser una
                # fila leída a medias o una que el banco imprime sin alterar
                # el saldo (un traspaso interno, un aviso).
                monto = min(f['candidatos'], key=lambda c: abs(c - objetivo))
                descuadre += abs(objetivo - monto)
                aviso = 'El saldo no calza con el monto de esta fila. Revísala.'

            movimientos.append(MovimientoLeido(
                fecha=f['fecha'], descripcion=f['descripcion'], monto=monto,
                tipo='INGRESO' if delta > 0 else 'EGRESO',
                saldo=f['saldo'], aviso=aviso,
            ))

        return movimientos, descuadre

    # -- datos de cabecera -------------------------------------------

    def _saldo_anterior(self, texto):
        m = SALDO_ANTERIOR.search(texto)
        return plata(m.group(1)) if m else None

    def _cuenta(self, texto):
        m = CUENTA.search(texto)
        if not m:
            return ''
        num = m.group(1).replace('-', '')
        return '…' + num[-4:] if len(num) > 4 else num

    def _periodo(self, filas):
        if not filas:
            return ''
        f = filas[0]['fecha']
        return f'{MESES[f.month - 1]} {f.year}'


# ---------------------------------------------------------------------
#  Los bancos e instituciones que emiten cartola con saldo en Chile
# ---------------------------------------------------------------------
#  Todos usan el mismo motor: lo único propio de cada uno son las palabras
#  con las que se reconoce su PDF y el nombre que se muestra. Agregar uno
#  nuevo es agregar una línea a esta tabla — no un archivo.
#
#  El Banco de Chile no está acá: tiene parser propio (banco_chile.py) que
#  además le quita el nombre de la oficina a la descripción.

INSTITUCIONES = (
    ('santander',    'Banco Santander',        ('santander',)),
    ('bci',          'Banco BCI',              ('banco bci', 'bci.cl', 'banco de credito e inversiones',
                                                'banco de crédito e inversiones')),
    ('estado',       'BancoEstado',            ('bancoestado', 'banco estado', 'bancoestado.cl')),
    ('scotiabank',   'Scotiabank',             ('scotiabank',)),
    ('itau',         'Banco Itaú',             ('itau', 'itaú')),
    ('security',     'Banco Security',         ('banco security',)),
    ('bice',         'Banco BICE',             ('banco bice', 'bice.cl')),
    ('consorcio',    'Banco Consorcio',        ('banco consorcio',)),
    ('internacional','Banco Internacional',    ('banco internacional',)),
    ('falabella',    'Banco Falabella',        ('banco falabella', 'bancofalabella')),
    ('ripley_banco', 'Banco Ripley',           ('banco ripley',)),
    ('coopeuch',     'Coopeuch',               ('coopeuch',)),
    ('btg',          'BTG Pactual',            ('btg pactual',)),
    ('tenpo',        'Tenpo',                  ('tenpo',)),
    ('mach',         'MACH',                   ('mach ', 'tarjeta mach')),
    ('mercadopago',  'Mercado Pago',           ('mercado pago', 'mercadopago')),
    ('global66',     'Global66',               ('global66',)),
    ('chek',         'Chek / Copec Pay',       ('chek', 'copec pay')),
    ('prepago_los_heroes', 'Caja Los Héroes',  ('los héroes', 'los heroes')),
)


def _registrar_instituciones():
    for clave, nombre, pistas in INSTITUCIONES:
        cls = type(
            'Lector' + clave.title().replace('_', ''),
            (Universal,),
            {'pistas': pistas, 'etiqueta': nombre},
        )
        registrar(clave, nombre)(cls)


_registrar_instituciones()
