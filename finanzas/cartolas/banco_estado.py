"""Cartola CuentaRUT de BancoEstado."""
import re
from datetime import date
from decimal import Decimal

from .base import Cartola, ErrorCartola, MovimientoLeido, plata, registrar

MES_ABREV = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'set': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}

INICIO_FILA = re.compile(r'\b(\d{1,2})\s*/\s*([A-Za-z]{3})\.?(?![a-zA-Z0-9])')
MONTO = re.compile(r'\$\s*(-?[\d.]+)')
OPERACION = re.compile(r'^\s*(?:n[°ºo]\.?\s*)?(\d{5,12})\b')
FECHA_DMA = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})')

CORTE = (
    'detalle de movimientos', 'operación', 'operacion', 'descripción',
    'descripcion', 'abonos', 'cargos', 'página', 'pagina',
    'saldo anterior', 'saldo final', 'total cargos', 'total abonos',
    'total giros', 'total depósitos', 'total depositos',
    'cartola seleccionada', 'fecha emisión', 'fecha emision',
    'fecha inicio', 'fecha final', 'de movimientos', 'cartola cuentarut',
    'bancoestado', 'n° cartola', 'nº cartola', 'nombre', 'rut',
)


@registrar('estado_cuentarut', 'BancoEstado CuentaRUT')
class BancoEstadoCuentaRut:

    def reconoce(self, texto):
        t = texto.lower()
        if 'cuentarut' not in t and 'cuenta rut' not in t:
            return False
        return 'detalle de movimientos' in t or 'cartola cuentarut' in t

    def parsear(self, texto):
        inicio, final = self._rango(texto)
        filas = self._filas(texto, inicio, final)

        if len(filas) < 2:
            raise ErrorCartola(
                'No encontré el detalle de movimientos de esta cartola '
                'CuentaRUT. Tiene que ser el PDF que descargas de BancoEstado, '
                'no una foto ni una captura de pantalla.'
            )

        if filas[0]['fecha'] < filas[-1]['fecha']:
            filas.reverse()

        saldo_anterior = self._cifra(texto, r'saldo\s+anterior')
        movimientos, descuadre = self._resolver(filas, saldo_anterior)

        cartola = Cartola(
            banco=self.nombre,
            movimientos=movimientos,
            periodo=self._periodo(inicio, final, filas),
            cuenta=self._cuenta(texto),
            saldo_inicial=saldo_anterior,
            saldo_final=self._cifra(texto, r'saldo\s+final'),
            descuadre=descuadre,
        )
        cartola.nota_cuadre = self._verificar(cartola, texto, descuadre)
        return cartola

    def _filas(self, texto, inicio, final):
        region = self._region(texto)
        marcas = list(INICIO_FILA.finditer(region))

        leidas = []
        for i, m in enumerate(marcas):
            hasta = marcas[i + 1].start() if i + 1 < len(marcas) else len(region)
            fila = self._fila(int(m.group(1)), m.group(2),
                              region[m.end():hasta], inicio, final)
            if fila:
                leidas.append(fila)
        return leidas

    def _region(self, texto):
        m = re.search(r'detalle\s+de\s+movimientos', texto, re.I)
        return texto[m.end():] if m else texto

    def _fila(self, dia, mes_txt, chunk, inicio, final):
        mes = MES_ABREV.get(mes_txt[:3].lower())
        if not mes:
            return None

        fecha = self._fecha(dia, mes, inicio, final)
        if not fecha:
            return None

        utiles = []
        for linea in chunk.splitlines():
            limpia = linea.strip()
            bajo = limpia.lower()
            if not limpia or ('$' not in limpia and any(c in bajo for c in CORTE)):
                continue
            utiles.append(limpia)
        plano = ' '.join(' '.join(utiles).split())

        cifras = list(MONTO.finditer(plano))
        if len(cifras) < 2:
            return None
        cifras = cifras[-3:]

        saldo = plata(cifras[-1].group(1))
        candidatos = []
        for c in cifras[:-1]:
            v = abs(plata(c.group(1)))
            if v and v not in candidatos:
                candidatos.append(v)
        if not candidatos:
            return None

        cabeza = plano[:cifras[0].start()]
        cola = plano[cifras[-1].end():]
        cabeza = OPERACION.sub('', cabeza, count=1)
        descripcion = ' '.join((cabeza + ' ' + cola).split())[:200]

        return {'fecha': fecha, 'descripcion': descripcion,
                'candidatos': candidatos, 'saldo': saldo}

    def _resolver(self, filas, saldo_anterior):
        movimientos, descuadre = [], Decimal(0)

        for i, f in enumerate(filas):
            previo = filas[i + 1]['saldo'] if i + 1 < len(filas) else saldo_anterior

            if previo is None:
                movimientos.append(MovimientoLeido(
                    fecha=f['fecha'], descripcion=f['descripcion'],
                    monto=f['candidatos'][0], tipo='EGRESO', saldo=f['saldo'],
                    aviso='Es el movimiento más antiguo y la cartola no declara '
                          'saldo anterior: confirma si entró o salió.',
                ))
                continue

            delta = f['saldo'] - previo
            objetivo = abs(delta)

            aviso = ''
            monto = next((c for c in f['candidatos'] if c == objetivo), None)
            if monto is None:
                monto = min(f['candidatos'], key=lambda c: abs(c - objetivo))
                descuadre += abs(objetivo - monto)
                aviso = 'El saldo no calza con el monto de esta fila. Revísala.'

            movimientos.append(MovimientoLeido(
                fecha=f['fecha'], descripcion=f['descripcion'], monto=monto,
                tipo='INGRESO' if delta > 0 else 'EGRESO',
                saldo=f['saldo'], aviso=aviso,
            ))

        return movimientos, descuadre

    def _verificar(self, cartola, texto, descuadre):
        n = len(cartola.movimientos)
        problemas = []

        declarados = self._entero(texto, r'n[°ºo]?\.?\s*de\s+movimientos')
        if declarados and declarados != n:
            problemas.append(
                f'la cartola declara {declarados} movimientos y leí {n}')

        cargos = self._cifra(texto, r'total\s+cargos')
        abonos = self._cifra(texto, r'total\s+abonos')
        if cargos is not None and abs(cartola.egresos - cargos) > 2:
            problemas.append('los cargos no suman el Total Cargos declarado')
        if abonos is not None and abs(cartola.ingresos - abonos) > 2:
            problemas.append('los abonos no suman el Total Abonos declarado')

        if cartola.saldo_final is not None and cartola.movimientos:
            if abs(cartola.movimientos[0].saldo - cartola.saldo_final) > 2:
                problemas.append('el último saldo no es el Saldo Final declarado')

        if descuadre:
            problemas.append('alguna fila no calza con la cadena de saldos')

        if not problemas:
            cartola.cuadra = True
            return (f'Los {n} movimientos cuadran con la cadena de saldos y con '
                    f'los totales que declara la cartola: los montos y los '
                    f'signos son correctos.')

        cartola.cuadra = False
        return ('Revisa antes de guardar: ' + '; '.join(problemas) + '.')

    def _rango(self, texto):
        inicio = self._fecha_campo(texto, r'fecha\s+inicio')
        final = self._fecha_campo(texto, r'fecha\s+final')
        emision = self._fecha_campo(texto, r'fecha\s+emisi[oó]n')
        return inicio, final or emision or inicio

    def _fecha(self, dia, mes, inicio, final):
        candidatos = []
        for ref in (inicio, final):
            if ref:
                candidatos += [ref.year, ref.year - 1, ref.year + 1]
        if not candidatos:
            candidatos = [date.today().year, date.today().year - 1]

        vistos, opciones = set(), []
        for anio in candidatos:
            if anio in vistos:
                continue
            vistos.add(anio)
            try:
                opciones.append(date(anio, mes, dia))
            except ValueError:
                continue
        if not opciones:
            return None

        if inicio and final:
            dentro = [f for f in opciones if inicio <= f <= final]
            if dentro:
                return dentro[0]
        ancla = final or inicio
        if ancla:
            return min(opciones, key=lambda f: abs((ancla - f).days))
        return opciones[0]

    def _fecha_campo(self, texto, etiqueta):
        m = re.search(etiqueta + r'[^\d]{0,20}(\d{1,2}/\d{1,2}/\d{4})',
                      texto, re.I)
        if not m:
            return None
        d, mes, a = FECHA_DMA.match(m.group(1)).groups()
        try:
            return date(int(a), int(mes), int(d))
        except ValueError:
            return None

    def _cifra(self, texto, etiqueta):
        m = re.search(etiqueta + r'[^\d\-]{0,20}(-?\d[\d.]*)', texto, re.I)
        return plata(m.group(1)) if m else None

    def _entero(self, texto, etiqueta):
        m = re.search(etiqueta + r'[^\d]{0,20}(\d{1,5})', texto, re.I)
        return int(m.group(1)) if m else None

    def _periodo(self, inicio, final, filas):
        meses = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
                 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
        ref = final or inicio or (filas[0]['fecha'] if filas else None)
        if not ref:
            return ''
        if inicio and final and (inicio.month, inicio.year) != (final.month, final.year):
            return (f'{meses[inicio.month - 1]} a {meses[final.month - 1]} '
                    f'{final.year}')
        return f'{meses[ref.month - 1]} {ref.year}'

    def _cuenta(self, texto):
        m = re.search(r'cartola\s+cuentarut\s*n?[°ºo]?\.?\s*(\d{5,15})',
                      texto, re.I)
        if not m:
            m = re.search(r'cuentarut[^\d]{0,20}(\d{5,15})', texto, re.I)
        if not m:
            return ''
        num = m.group(1)
        return '…' + num[-4:] if len(num) > 4 else num
