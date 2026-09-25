import re
from datetime import datetime

from .base import Cartola, ErrorCartola, MovimientoLeido, plata, registrar

FILA = re.compile(
    r'^(.*?)\s*'
    r'(\d{2}/\d{2}/\d{4})\s+'
    r'(.+?)\s+'
    r'(T|A\d)\s+'
    r'(-?[\d.]+)\s+'
    r'(-?[\d.]+)\s+'
    r'(\d{1,2})/(\d{1,2})'
    r'(?:\s+([a-zA-Z]{3}-\d{4})\s+(-?[\d.]+))?'
    r'\s*$'
)

CARGO = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$')

FACTURADO = re.compile(r'Monto\s+Total\s+Facturado\s+a\s+Pagar\s+(-?[\d.]+)', re.I)
FECHA_FACT = re.compile(r'Fecha\s+Facturaci[oó]n[^:]*:\s*(\d{2}/\d{2}/\d{4})', re.I)
CONTRATO = re.compile(r'N[°º]\s*de\s*Contrato:\s*([\d*]+)', re.I)

NO_ES_GASTO = ('pago tarjeta', 'pago recibido', 'abono pago')

MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')


@registrar('cmr', 'CMR / Banco Falabella (tarjeta)')
class CMR:

    es_tarjeta = True

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

        if facturado:
            diferencia = abs(suma - facturado)
            cartola.descuadre = diferencia
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
