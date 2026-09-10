"""Cartola de cuenta corriente del Banco de Chile.

Formato de una fila, ya extraída del PDF:

    31/08/2026 CENTRO DE Transf. de LOPEZ VARGAS ANA MARIA $ 49.200 $ 713.551
    \_______/ \________/ \_____________________________/ \______/ \_______/
      fecha     oficina              descripción            monto    saldo

La oficina se pega a la descripción porque la columna 'Nro Doc' viene vacía
y al extraer el texto las columnas vacías no dejan rastro. Se le quita por
nombre conocido; si aparece una oficina nueva, lo peor que pasa es que su
nombre queda como prefijo de la descripción, no que la fila se pierda.
"""
import re
from datetime import datetime
from decimal import Decimal

from .base import Cartola, ErrorCartola, plata, registrar, resolver_signos

# Una fila entera. Se busca sobre todo el texto y no línea por línea: cómo
# corta las líneas depende de la versión de pypdf, pero la forma de la fila
# (fecha ... $ monto $ saldo) es del documento y no cambia.
FILA = re.compile(
    r'(\d{2}/\d{2}/\d{4})\s+'          # fecha
    r'(.+?)\s+'                          # oficina + descripción
    r'\$\s*([\d.]+)\s+'                 # monto (cargo o abono, aún sin saber)
    r'\$\s*(-?[\d.]+)'                   # saldo corrido
)

OFICINAS = ('CASA MATRIZ', 'CENTRO DE', 'INTERNET', 'SUCURSAL')


@registrar('banco_chile', 'Banco de Chile')
class BancoChile:

    def reconoce(self, texto):
        t = texto.lower()
        return 'detalle de movimientos' in t and (
            'cartola histórica' in t or 'cartola historica' in t
            or 'saldo contable' in t
        )

    def parsear(self, texto):
        saldo_inicial, saldo_contable = self._saldos(texto)

        filas = []
        for m in FILA.finditer(texto):
            fecha_txt, desc, monto_txt, saldo_txt = m.groups()
            try:
                fecha = datetime.strptime(fecha_txt, '%d/%m/%Y').date()
            except ValueError:
                continue
            filas.append({
                'fecha': fecha,
                'descripcion': self._limpiar(desc),
                'monto': plata(monto_txt),
                'saldo': plata(saldo_txt),
            })

        if not filas:
            raise ErrorCartola(
                'No encontré movimientos en el PDF. Si lo escaneaste o le '
                'sacaste una foto, no sirve: tiene que ser el PDF que '
                'descarga el banco.'
            )

        movimientos, descuadre = resolver_signos(filas, saldo_inicial)

        cartola = Cartola(
            banco=self.nombre,
            movimientos=movimientos,
            periodo=self._periodo(texto),
            cuenta=self._cuenta(texto),
            saldo_inicial=saldo_inicial,
            saldo_final=saldo_contable,
            descuadre=descuadre,
        )

        # El cierre completo: el saldo del movimiento más nuevo tiene que ser
        # el Saldo Contable que la cartola declara arriba. Si las dos cifras
        # no coinciden es que se perdieron filas al extraer el texto, y
        # importar una cartola incompleta es peor que no importar nada.
        if saldo_contable is not None and filas[0]['saldo'] != saldo_contable:
            cartola.cuadra = False
            cartola.descuadre = abs(filas[0]['saldo'] - saldo_contable)
        elif descuadre:
            cartola.cuadra = False

        cartola.nota_cuadre = (
            f'Los saldos de las {len(filas)} filas encajan uno con otro y con el '
            f'saldo que declara el banco, así que no falta ningún movimiento.'
            if cartola.cuadra else
            'Hay una diferencia entre lo leído y lo que declara el banco: '
            'probablemente se perdieron filas al extraer el texto.'
        )
        return cartola

    # -- piezas ------------------------------------------------------

    def _limpiar(self, desc):
        d = ' '.join(desc.split())
        for of in OFICINAS:
            if d.upper().startswith(of):
                d = d[len(of):].strip()
                break
        # Un número de documento suelto al principio no aporta nada.
        d = re.sub(r'^\d{4,}\s+', '', d)
        return d[:200]

    def _saldos(self, texto):
        """Saldo Inicial y Saldo Contable, del recuadro de arriba.

        Vienen en una fila de cuatro cifras bajo sus títulos:
            Saldo Inicial  Saldo Contable  Retenciones  Saldo Disponible
            $ 584.700      $ 703.551       $ 0          $ 703.551
        """
        m = re.search(
            r'Saldo\s+Inicial.*?\$\s*(-?[\d.]+)\s+\$\s*(-?[\d.]+)',
            texto, re.S | re.I,
        )
        if not m:
            return None, None
        return plata(m.group(1)), plata(m.group(2))

    def _periodo(self, texto):
        m = re.search(
            r'(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|'
            r'Septiembre|Octubre|Noviembre|Diciembre)\s+(\d{4})',
            texto, re.I,
        )
        return f'{m.group(1)} {m.group(2)}' if m else ''

    def _cuenta(self, texto):
        m = re.search(r'\b(\d{2}-\d{3}-\d{6}-\d)\b', texto)
        if not m:
            return ''
        # Solo los últimos cuatro dígitos: no hay razón para volver a
        # escribir el número de cuenta completo en pantalla.
        return '…' + m.group(1)[-4:]
