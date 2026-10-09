from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from ..cartolas import BANCOS
from ..cartolas.base import ErrorCartola

CARTOLA = """ESTADO DE CUENTA TARJETA RIPLEY
MONTO TOTAL FACTURADO A PAGAR $ 68.450
FECHA ESTADO DE CUENTA 20/SEP/2026
N° DE TARJETA: XXXX-XXXX-XXXX-4321
DETALLE DE OPERACIONES
SUPERMERCADO SANTA ISABEL 12/SEP/2026 23.450
02/06 ZAPATILLAS DEPORTIVAS 15/JUL/2026 45.000
PAGO EN LINEA 10/SEP/2026 -80.000
TOTAL OPERACIONES 68.450 (B)
TOTAL PAGOS -80.000 (C)
2.4. TRANSACCIONES NO FACTURADAS
ZAPATERIA 18/SEP/2026 9.990
"""


class RipleyTests(SimpleTestCase):

    def leer(self, texto=CARTOLA):
        return BANCOS['ripley']().parsear(texto)

    def movimiento(self, inicio):
        return next(m for m in self.leer().movimientos if m.descripcion.startswith(inicio))

    def test_reconoce_el_formato_antes_que_otro_lector(self):
        reconocen = [c for c, lector in BANCOS.items() if lector().reconoce(CARTOLA)]
        self.assertEqual(reconocen[0], 'ripley')

    def test_deja_fuera_lo_que_todavia_no_se_factura(self):
        descripciones = [m.descripcion for m in self.leer().movimientos]
        self.assertEqual(len(descripciones), 3)
        self.assertFalse(any('ZAPATERIA' in d for d in descripciones))

    def test_la_cuota_se_lee_al_inicio_de_la_fila(self):
        cuota = self.movimiento('ZAPATILLAS')
        self.assertEqual(cuota.descripcion, 'ZAPATILLAS DEPORTIVAS · cuota 2 de 6')
        self.assertEqual((cuota.cuota_actual, cuota.cuota_total), (2, 6))
        self.assertEqual(cuota.fecha, date(2026, 9, 20))
        self.assertEqual(cuota.monto, Decimal('45000'))
        self.assertIn('15/07/2026', cuota.aviso)

    def test_un_monto_negativo_es_un_pago_y_no_un_gasto(self):
        pago = self.movimiento('PAGO EN LINEA')
        self.assertEqual(pago.monto, Decimal('80000'))
        self.assertIn('No es un gasto', pago.aviso)
        compra = self.movimiento('SUPERMERCADO')
        self.assertEqual((compra.fecha, compra.monto), (date(2026, 9, 12), Decimal('23450')))

    def test_cuadra_con_los_subtotales_del_estado_de_cuenta(self):
        cartola = self.leer()
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)
        self.assertIn('subtotales', cartola.nota_cuadre)
        self.assertEqual(cartola.saldo_final, Decimal('68450'))
        self.assertEqual(cartola.periodo, 'Septiembre 2026')
        self.assertEqual(cartola.cuenta, '…4321')

    def test_una_diferencia_chica_se_avisa(self):
        cartola = self.leer(CARTOLA.replace('ISABEL 12/SEP/2026 23.450', 'ISABEL 12/SEP/2026 23.000'))
        self.assertFalse(cartola.cuadra)
        self.assertEqual(cartola.descuadre, Decimal('450'))

    def test_una_diferencia_grande_pide_revisar_el_formato(self):
        with self.assertRaises(ErrorCartola):
            self.leer(CARTOLA.replace('PAGO EN LINEA 10/SEP/2026 -80.000\n', ''))
