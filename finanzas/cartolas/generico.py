"""El intento para bancos sin parser propio.

POR QUÉ ES SEGURO INTENTARLO
----------------------------
El truco del saldo corrido no es del Banco de Chile: es de la contabilidad.
Cualquier cartola cuyas filas tengan la forma

    fecha   descripción   monto   saldo

se puede resolver igual, porque la resta entre saldos consecutivos da el
signo del movimiento. Este parser busca esa forma sin saber de qué banco es.

Adivinar sería peligroso si el error fuera silencioso. No lo es: cada fila
se comprueba contra la resta de saldos, y si el formato no era el supuesto,
las cuentas no dan. Con menos de 90% de filas cuadradas el archivo se
rechaza en vez de entregar movimientos inventados. Y las que pasan llegan a
la pantalla de revisión con el aviso de cuadre en verde o en rojo.

Dicho de otro modo: este parser no promete leer tu banco. Promete que si no
puede, te lo va a decir.

LO QUE NO PUEDE SABER
---------------------
El movimiento más viejo de la cartola es el único sin fila anterior contra
la cual restar. Si el PDF declara un "saldo anterior" se usa ese; si no, esa
sola fila queda marcada para que la revises. Las demás son exactas.
"""
import re
from datetime import datetime
from decimal import Decimal

from .base import Cartola, ErrorCartola, plata, registrar, resolver_signos

FECHA = re.compile(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b')

# Una cifra de plata: con o sin $, con puntos de miles y coma decimal
# opcional. El lookbehind y el lookahead evitan morder pedazos de una fecha
# o de un número de documento pegado a otro.
CIFRA = re.compile(r'(?<![\d/.-])(\$\s*)?(-?\d[\d.]*(?:,\d{1,2})?)(?![\d/.-])')

# El saldo de arranque, cuando la cartola lo declara. La ventana es ancha y
# admite cualquier cosa en el medio porque los encabezados de las otras
# columnas — y a veces el número de cuenta — se cruzan entre el título y la
# cifra. Se exige el signo peso para no agarrar el primer número que pase.
#
# Arriesgar aquí no cuesta nada: si agarra la cifra equivocada, la resta de
# saldos del movimiento más antiguo deja de calzar y esa fila llega marcada.
SALDO_ANTERIOR = re.compile(
    r'saldo\s+(?:inicial|anterior|previo)[\s\S]{0,220}?\$\s*(-?\d[\d.]*(?:,\d{1,2})?)',
    re.I,
)

# Pistas para la única fila que la cadena no puede resolver sola.
ENTRA = ('abono', 'deposito', 'depósito', 'transf. de', 'transf de',
         'transferencia de', 'transferencia desde', 'remuneracion',
         'remuneración', 'sueldo', 'devolucion', 'devolución', 'reverso',
         'pago recibido', 'haberes')


@registrar('generico', 'Otro banco (intento genérico)')
class Generico:

    def reconoce(self, texto):
        # Nunca se ofrece solo: leer_cartola lo usa como último recurso, y en
        # el selector el usuario lo puede elegir a mano. Si respondiera True
        # se comería las cartolas que otro parser lee mejor.
        return False

    def parsear(self, texto):
        filas = self._filas(texto)
        if len(filas) < 3:
            raise ErrorCartola(
                'No encontré una tabla de movimientos en este PDF. Si es un '
                'escaneo o una foto no sirve: tiene que ser el PDF que '
                'descarga el banco.'
            )

        filas = self._ordenar(filas)
        saldo_inicial = self._saldo_anterior(texto)

        # La prueba: ¿la resta de saldos reproduce el monto impreso? Se mide
        # antes de entregar nada. Es lo que separa "leí tu cartola" de
        # "encontré números y los ordené".
        aciertos = 0
        for i, f in enumerate(filas[:-1]):
            if abs(f['saldo'] - filas[i + 1]['saldo']) == f['monto']:
                aciertos += 1

        comparables = len(filas) - 1
        if comparables and aciertos / comparables < 0.9:
            raise ErrorCartola(
                'Encontré filas con fechas y montos, pero los saldos no '
                'siguen una cadena coherente: este formato necesita un lector '
                'propio. Mándame el PDF y lo agrego.'
            )

        movimientos, descuadre = resolver_signos(filas, saldo_inicial)

        # La fila más vieja, si no hubo saldo anterior declarado, se resolvió
        # a ciegas. Se le pone la mejor pista disponible y se marca.
        if saldo_inicial is None and movimientos:
            ultimo = movimientos[-1]
            bajo = ultimo.descripcion.lower()
            if any(p in bajo for p in ENTRA):
                ultimo.tipo = 'INGRESO'
            ultimo.aviso = ('Es el movimiento más antiguo y no hay saldo '
                            'anterior contra el cual compararlo: confirma si '
                            'entró o salió.')

        cartola = Cartola(
            banco='Cartola genérica',
            movimientos=movimientos,
            periodo=self._periodo(filas),
            saldo_inicial=saldo_inicial,
            saldo_final=filas[0]['saldo'],
            descuadre=descuadre,
            cuadra=not descuadre,
        )
        cartola.nota_cuadre = (
            f'Leí este PDF sin conocer el formato del banco, pero los saldos de '
            f'las {len(filas)} filas forman una cadena coherente: los montos y los '
            f'signos son correctos.'
            if cartola.cuadra else
            'Leí este PDF sin conocer el formato del banco y algunas filas no '
            'calzan con la cadena de saldos. Revisa las marcadas.'
        )
        return cartola

    # -- piezas ------------------------------------------------------

    def _filas(self, texto):
        filas = []
        for linea in texto.splitlines():
            m = FECHA.search(linea)
            if not m:
                continue
            fecha = self._fecha(m)
            if not fecha:
                continue

            resto = linea[m.end():]
            cifras = list(CIFRA.finditer(resto))

            # Cuando la línea marca algunas cifras con $, esas son las de
            # plata y el resto son números sueltos de la descripción (el
            # local de la compra, el número de documento).
            con_signo = [c for c in cifras if c.group(1)]
            if len(con_signo) >= 2:
                cifras = con_signo
            if len(cifras) < 2:
                continue

            monto = plata(cifras[-2].group(2))
            saldo = plata(cifras[-1].group(2))
            if monto <= 0:
                continue

            filas.append({
                'fecha': fecha,
                'descripcion': ' '.join(resto[:cifras[-2].start()].split())[:200],
                'monto': monto,
                'saldo': saldo,
            })
        return filas

    def _fecha(self, m):
        d, mes, a = (int(x) for x in m.groups())
        if a < 100:
            a += 2000
        try:
            return datetime(a, mes, d).date()
        except ValueError:
            # Puede haber salido dd/mm invertido, o no ser una fecha.
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

    def _saldo_anterior(self, texto):
        m = SALDO_ANTERIOR.search(texto)
        return plata(m.group(1)) if m else None

    def _periodo(self, filas):
        if not filas:
            return ''
        f = filas[0]['fecha']
        meses = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
                 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')
        return f'{meses[f.month - 1]} {f.year}'
