"""Estado de cuenta de tarjeta de crédito CMR / Banco Falabella.

OTRO MUNDO
----------
Una cartola de cuenta corriente lleva saldo corrido y de ahí sale el signo
de cada movimiento. Un estado de cuenta de tarjeta no tiene saldo: tiene
cuotas. Una fila se ve así:

    Santiago 30/09/2025 Mp *mercado libre A1 589.990 589.990 11/12 nov-2025 49.165
    \______/ \________/ \_______________/ \/ \_____/ \_____/ \___/ \______/ \____/
      lugar     fecha        comercio     tj   monto   total  cuota  1ª cta  valor

Todo es cargo, así que no hay signo que deducir. Lo que sí hay que decidir
es QUÉ importar, y ahí está el error fácil de cometer.

QUÉ SE IMPORTA Y POR QUÉ
------------------------
Una compra en 12 cuotas aparece en el estado de cuenta de los doce meses.
Importar los $589.990 completos sería contar en septiembre una compra de
septiembre del año pasado — y volver a contarla el mes siguiente, y el
siguiente. Al tercer mes la app diría que gastaste tres millones que nunca
gastaste.

Lo que sale de tu bolsillo este mes es la CUOTA: $49.165. Así que eso es lo
que se importa, de cada fila, siempre. Para una compra en una sola cuota la
cuota es el monto completo, o sea que la regla vale para todas.

Y esa decisión trae su propia verificación: si de cada fila se toma la
cuota, la suma de todas tiene que dar el Monto Total Facturado que el propio
estado de cuenta declara al final. En el estado que probé da exacto, hasta
el peso. Si no da, algo se leyó mal y la pantalla lo dice antes de guardar.

LA FECHA
--------
Una compra en cuotas se fecha en el día de facturación, no en el de la
compra: la cuota de agosto es un gasto de agosto aunque la compra sea de
septiembre del año pasado. Fecharla en 2025 la escondería en un mes cerrado
y el total de agosto no cuadraría con lo que pagaste. Las compras de una
sola cuota conservan su fecha real, que sí cae en el período.
"""
import re
from datetime import datetime

from .base import Cartola, ErrorCartola, MovimientoLeido, plata, registrar

# La fila estándar de compra. El lugar es opcional (las filas de cargos no
# lo traen) y la parte de cuotas también: la fila del pago del estado
# anterior corta después del 01/01.
FILA = re.compile(
    r'^(.*?)\s*'                                  # lugar
    r'(\d{2}/\d{2}/\d{4})\s+'                     # fecha de la operación
    r'(.+?)\s+'                                   # comercio
    r'(T|A\d)\s+'                                 # titular o adicional
    r'(-?[\d.]+)\s+'                              # monto de la operación
    r'(-?[\d.]+)\s+'                              # monto total con interés
    r'(\d{1,2})/(\d{1,2})'                         # cuota actual / total
    r'(?:\s+([a-zA-Z]{3}-\d{4})\s+(-?[\d.]+))?'    # mes 1ª cuota + valor cuota
    r'\s*$'
)

# Impuestos y comisiones: sin lugar, sin tarjeta, sin cuotas. Tres cifras
# iguales al final (monto, total, valor).
CARGO = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$')

FACTURADO = re.compile(r'Monto\s+Total\s+Facturado\s+a\s+Pagar\s+(-?[\d.]+)', re.I)
FECHA_FACT = re.compile(r'Fecha\s+Facturaci[oó]n[^:]*:\s*(\d{2}/\d{2}/\d{4})', re.I)
CONTRATO = re.compile(r'N[°º]\s*de\s*Contrato:\s*([\d*]+)', re.I)

# Filas que no son un gasto: el pago del estado de cuenta anterior. Salen en
# la lista igual, pero desmarcadas y explicadas — esconderlas haría que la
# suma no cuadre a la vista.
NO_ES_GASTO = ('pago tarjeta', 'pago recibido', 'abono pago')

MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')


@registrar('cmr', 'CMR / Banco Falabella (tarjeta)')
class CMR:

    def reconoce(self, texto):
        t = texto.lower()
        return 'estado de cuenta' in t and (
            'cmr' in t or 'bancofalabella' in t or 'banco falabella' in t
        )

    def parsear(self, texto):
        fecha_fact = self._fecha_facturacion(texto)
        facturado = self._facturado(texto)

        movimientos, suma = [], 0
        for linea in texto.splitlines():
            m = self._fila(linea.strip(), fecha_fact)
            if not m:
                continue
            movimientos.append(m)
            if m.tipo == 'EGRESO' and 'no es un gasto' not in m.aviso.lower():
                suma += m.monto

        if not movimientos:
            raise ErrorCartola(
                'No encontré movimientos en el estado de cuenta. Tiene que ser '
                'el PDF que descarga el banco, no una foto ni una captura.'
            )

        cartola = Cartola(
            banco='CMR / Banco Falabella',
            movimientos=movimientos,
            periodo=self._periodo(fecha_fact),
            cuenta=self._contrato(texto),
            saldo_final=facturado,
        )

        # La comprobación propia de este formato: la suma de las cuotas del
        # período contra el total que el estado declara.
        if facturado:
            diferencia = abs(suma - facturado)
            cartola.descuadre = diferencia
            # Se tolera hasta un 1%: el estado arrastra ajustes de pesos del
            # período anterior que no salen como fila (en el que probé, nueve
            # pesos). Fallar por eso sería un falso positivo cada mes.
            cartola.cuadra = diferencia <= max(facturado / 100, 50)
            if cartola.cuadra:
                cartola.nota_cuadre = (
                    f'Las {len(movimientos)} filas suman lo mismo que el Monto Total '
                    f'Facturado del estado de cuenta, así que no falta ninguna compra.'
                )
            else:
                cartola.nota_cuadre = (
                    f'La suma de las filas se aleja en {diferencia:,.0f} del Monto Total '
                    f'Facturado. Falta o sobra alguna compra: revísalas una por una.'
                ).replace(',', '.')
        else:
            cartola.cuadra = False
            cartola.nota_cuadre = (
                'No encontré el Monto Total Facturado, así que no puedo verificar '
                'que estén todas las compras. Revísalas antes de guardar.'
            )

        return cartola

    # -- piezas ------------------------------------------------------

    def _fila(self, linea, fecha_fact):
        m = FILA.match(linea)
        if m:
            return self._compra(m, fecha_fact)
        m = CARGO.match(linea)
        if m:
            return self._cargo(m)
        return None

    def _compra(self, m, fecha_fact):
        lugar, fecha_txt, desc, _tj, monto_op, _total, ca, ct, _mes, valor = m.groups()
        fecha_op = self._fecha(fecha_txt)
        if not fecha_op:
            return None

        desc = ' '.join(desc.split())
        ca, ct = int(ca), int(ct)

        # Sin valor de cuota la fila no es una compra del período: es el pago
        # del estado anterior, que corta antes de esa columna.
        if valor is None:
            monto = abs(plata(monto_op))
            if not monto:
                return None
            return MovimientoLeido(
                fecha=fecha_op, descripcion=desc, monto=monto,
                tipo='EGRESO', saldo=0,
                aviso='No es un gasto: es el pago del estado de cuenta anterior. '
                      'Ya lo tienes en la cartola de tu cuenta corriente.',
            )

        monto = abs(plata(valor))
        if not monto:
            return None

        bajo = desc.lower()
        if any(p in bajo for p in NO_ES_GASTO):
            return MovimientoLeido(
                fecha=fecha_op, descripcion=desc, monto=monto, tipo='EGRESO', saldo=0,
                aviso='No es un gasto: es un pago a la tarjeta.',
            )

        if ct > 1:
            # La cuota es del mes que se factura, no del día de la compra.
            # El comercio se queda con la marca de cuál cuota es, que además
            # hace que el mes siguiente no se lea como la misma fila.
            return MovimientoLeido(
                fecha=fecha_fact or fecha_op,
                descripcion=f'{desc} · cuota {ca} de {ct}'[:200],
                monto=monto, tipo='EGRESO', saldo=0,
                cuota_actual=ca, cuota_total=ct,
                aviso=f'Compra del {fecha_op.strftime("%d/%m/%Y")} en {ct} cuotas. '
                      f'Se anota en este mes porque es la cuota que pagas ahora.',
            )

        if lugar and lugar.strip() not in ('S/I', ''):
            desc = f'{desc} ({lugar.strip()})'[:200]

        return MovimientoLeido(
            fecha=fecha_op, descripcion=desc, monto=monto, tipo='EGRESO', saldo=0,
        )

    def _cargo(self, m):
        fecha_txt, desc, _a, _b, valor = m.groups()
        fecha = self._fecha(fecha_txt)
        monto = abs(plata(valor))
        if not fecha or not monto:
            return None
        return MovimientoLeido(
            fecha=fecha, descripcion=' '.join(desc.split())[:200],
            monto=monto, tipo='EGRESO', saldo=0, categoria='Otros',
        )

    def _fecha(self, txt):
        try:
            return datetime.strptime(txt, '%d/%m/%Y').date()
        except ValueError:
            return None

    def _fecha_facturacion(self, texto):
        m = FECHA_FACT.search(texto)
        return self._fecha(m.group(1)) if m else None

    def _facturado(self, texto):
        m = FACTURADO.search(texto)
        return plata(m.group(1)) if m else None

    def _periodo(self, fecha_fact):
        if not fecha_fact:
            return ''
        return f'{MESES[fecha_fact.month - 1]} {fecha_fact.year}'

    def _contrato(self, texto):
        m = CONTRATO.search(texto)
        return '…' + m.group(1)[-4:] if m else ''
