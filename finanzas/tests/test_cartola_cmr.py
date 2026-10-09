from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from ..cartolas import BANCOS

CARTOLA = """ESTADO DE CUENTA TARJETA CMR
N° de Contrato: ****1234
Fecha Facturación: 25/09/2026
Monto Total Facturado a Pagar 116.970
SANTIAGO 03/09/2026 FARMACIA CRUZ VERDE T 12.990 12.990 01/01 oct-2026 12.990
S/I 10/08/2026 FALABELLA TV T 299.970 299.970 02/03 oct-2026 99.990
S/I 05/09/2026 PAGO TARJETA CMR T -150.000 -150.000 01/01
30/09/2026 COMISION MENSUAL 0 0 3.990
"""


class CMRTests(SimpleTestCase):

    def leer(self, texto=CARTOLA):
        return BANCOS['cmr']().parsear(texto)

    def movimiento(self, inicio):
        return next(m for m in self.leer().movimientos if m.descripcion.startswith(inicio))

    def test_reconoce_el_formato_antes_que_otro_lector(self):
        reconocen = [c for c, lector in BANCOS.items() if lector().reconoce(CARTOLA)]
        self.assertEqual(reconocen[0], 'cmr')

    def test_lee_compras_cuotas_pagos_y_cargos(self):
        movs = self.leer().movimientos
        self.assertEqual(len(movs), 4)
        self.assertTrue(all(m.tipo == 'EGRESO' for m in movs))

    def test_la_cuota_se_anota_en_el_mes_de_facturacion(self):
        cuota = self.movimiento('FALABELLA TV')
        self.assertEqual(cuota.descripcion, 'FALABELLA TV · cuota 2 de 3')
        self.assertEqual(cuota.fecha, date(2026, 9, 25))
        self.assertEqual(cuota.monto, Decimal('99990'))
        self.assertEqual((cuota.cuota_actual, cuota.cuota_total), (2, 3))
        self.assertIn('10/08/2026', cuota.aviso)

    def test_el_pago_del_estado_anterior_no_es_un_gasto(self):
        pago = self.movimiento('PAGO TARJETA CMR')
        self.assertEqual(pago.monto, Decimal('150000'))
        self.assertIn('No es un gasto', pago.aviso)

    def test_una_compra_al_contado_lleva_el_lugar(self):
        compra = self.movimiento('FARMACIA')
        self.assertEqual(compra.descripcion, 'FARMACIA CRUZ VERDE (SANTIAGO)')
        self.assertEqual(compra.fecha, date(2026, 9, 3))
        self.assertEqual(self.movimiento('COMISION').categoria, 'Otros')

    def test_cuadra_con_el_monto_total_facturado(self):
        cartola = self.leer()
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)
        self.assertEqual(cartola.saldo_final, Decimal('116970'))
        self.assertTrue(cartola.periodo.startswith('Septiembre 2026 · ciclo del'))
        self.assertEqual(cartola.cuenta, '…1234')

    def test_avisa_cuando_falta_una_compra(self):
        recortada = CARTOLA.replace(
            'SANTIAGO 03/09/2026 FARMACIA CRUZ VERDE T 12.990 12.990 01/01 oct-2026 12.990\n', '')
        cartola = self.leer(recortada)
        self.assertFalse(cartola.cuadra)
        self.assertIn('se aleja', cartola.nota_cuadre)

    def test_sin_el_monto_facturado_no_puede_verificar(self):
        cartola = self.leer(CARTOLA.replace('Monto Total Facturado a Pagar 116.970\n', ''))
        self.assertFalse(cartola.cuadra)
        self.assertIn('No encontré el Monto Total Facturado', cartola.nota_cuadre)
