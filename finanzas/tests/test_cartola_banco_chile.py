from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from ..cartolas import BANCOS
from ..cartolas.base import ErrorCartola

CARTOLA = """Banco de Chile
Cartola Histórica
Cuenta Corriente N° 00-123-456789-0
Periodo Septiembre 2026
Saldo Inicial Saldo Contable
$ 500.000 $ 1.155.010
Detalle de Movimientos
Fecha Descripción Monto Saldo
28/09/2026 INTERNET PAGO TARJETA DE CREDITO $ 120.000 $ 1.155.010
25/09/2026 CASA MATRIZ 0012345 TRASPASO DE CAMILA ROJAS $ 35.000 $ 1.275.010
15/09/2026 COMPRA WEBPAY SUPERMERCADO $ 54.990 $ 1.240.010
01/09/2026 INTERNET REMUNERACION EMPRESA SPA $ 795.000 $ 1.295.000
"""


class BancoChileTests(SimpleTestCase):

    def leer(self, texto=CARTOLA):
        return BANCOS['banco_chile']().parsear(texto)

    def test_reconoce_el_formato_antes_que_otro_lector(self):
        reconocen = [c for c, lector in BANCOS.items() if lector().reconoce(CARTOLA)]
        self.assertEqual(reconocen[0], 'banco_chile')

    def test_lee_las_filas_y_quita_la_oficina_y_el_numero(self):
        movs = self.leer().movimientos
        self.assertEqual(len(movs), 4)
        self.assertEqual([m.descripcion for m in movs], [
            'PAGO TARJETA DE CREDITO', 'TRASPASO DE CAMILA ROJAS',
            'COMPRA WEBPAY SUPERMERCADO', 'REMUNERACION EMPRESA SPA'])
        self.assertEqual(movs[0].fecha, date(2026, 9, 28))

    def test_deduce_el_signo_con_la_cadena_de_saldos(self):
        movs = {m.descripcion: m for m in self.leer().movimientos}
        self.assertEqual(movs['REMUNERACION EMPRESA SPA'].tipo, 'INGRESO')
        self.assertEqual(movs['TRASPASO DE CAMILA ROJAS'].tipo, 'INGRESO')
        self.assertEqual(movs['COMPRA WEBPAY SUPERMERCADO'].tipo, 'EGRESO')
        self.assertEqual(movs['PAGO TARJETA DE CREDITO'].monto, Decimal('120000'))

    def test_cuadra_con_los_saldos_que_declara_el_banco(self):
        cartola = self.leer()
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)
        self.assertEqual(cartola.saldo_inicial, Decimal('500000'))
        self.assertEqual(cartola.saldo_final, Decimal('1155010'))
        self.assertEqual(cartola.ingresos, Decimal('830000'))
        self.assertEqual(cartola.egresos, Decimal('174990'))
        self.assertEqual(cartola.periodo, 'Septiembre 2026')
        self.assertEqual(cartola.cuenta, '…89-0')

    def test_avisa_cuando_falta_una_fila(self):
        recortada = CARTOLA.replace(
            '15/09/2026 COMPRA WEBPAY SUPERMERCADO $ 54.990 $ 1.240.010\n', '')
        cartola = self.leer(recortada)
        self.assertFalse(cartola.cuadra)
        self.assertIn('diferencia', cartola.nota_cuadre)

    def test_rechaza_un_pdf_sin_movimientos(self):
        with self.assertRaises(ErrorCartola):
            self.leer('Banco de Chile\nCartola Histórica\nDetalle de Movimientos\n')
