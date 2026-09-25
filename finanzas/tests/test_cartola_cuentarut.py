from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from ..cartolas import BANCOS
from ..cartolas.base import ErrorCartola

CARTOLA = """CARTOLA CUENTARUT N° 20344444
Cliente
Nombre RUT Fecha y Hora
CORTEZ GONZALEZ MARIA FERNANDA 16/09/2026 15:22
Movimientos
Cartola Seleccionada 000022 14/08/2026
Saldo
N° Cartola 000022 Fecha Emisión 14/08/2026
N° de Movimientos 6 Saldo Anterior $ 478.527
Fecha Inicio 06/08/2026 Fecha Final 14/08/2026
Total Giros $ Total Cargos $ 83.980
Total Depósitos $ Total Abonos $ 187.390
Saldo Final $ 581.937
Detalle de movimientos:
Fecha N°
Operación Descripción Abonos Cargos Saldo
06/Ago 8019968 TEF DE JUAN
CARVAJAL $36.790 $515.317
06/Ago 8095580 TEF A MARIA FERNANDA CORTEZ $31.990 $483.327
GONZALEZ
06/Ago 8049936 PAGO WEBPAY EPARIS $44.990 $438.337
06/Ago 8012264 TEF A JOSE
FIGUEROA $7.000 $431.337
06/Ago 8059234 TEF DE PEDRO
LARA $3.600 $434.937
07/Ago 8019467 DEP EN EFECTIVO CAJA VECINA $147.000 $581.937
"""


class CuentaRutTests(SimpleTestCase):

    def leer(self, texto=CARTOLA):
        return BANCOS['estado_cuentarut']().parsear(texto)

    def test_reconoce_el_formato(self):
        self.assertTrue(BANCOS['estado_cuentarut']().reconoce(CARTOLA))

    def test_lee_todas_las_filas(self):
        self.assertEqual(len(self.leer().movimientos), 6)

    def test_completa_el_anio_que_la_fila_no_trae(self):
        fechas = {m.fecha for m in self.leer().movimientos}
        self.assertEqual(fechas, {date(2026, 8, 6), date(2026, 8, 7)})

    def test_deduce_el_signo_con_la_cadena_de_saldos(self):
        movs = {m.descripcion: m for m in self.leer().movimientos}
        self.assertEqual(movs['TEF DE JUAN CARVAJAL'].tipo, 'INGRESO')
        self.assertEqual(movs['TEF DE JUAN CARVAJAL'].monto, Decimal('36790'))
        self.assertEqual(movs['PAGO WEBPAY EPARIS'].tipo, 'EGRESO')
        self.assertEqual(movs['DEP EN EFECTIVO CAJA VECINA'].tipo, 'INGRESO')

    def test_junta_la_descripcion_partida_en_dos_lineas(self):
        descripciones = [m.descripcion for m in self.leer().movimientos]
        self.assertIn('TEF A MARIA FERNANDA CORTEZ GONZALEZ', descripciones)

    def test_quita_el_numero_de_operacion_de_la_descripcion(self):
        for m in self.leer().movimientos:
            self.assertFalse(m.descripcion.startswith('80'), m.descripcion)

    def test_cuadra_contra_los_totales_declarados(self):
        cartola = self.leer()
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)
        self.assertEqual(cartola.ingresos, Decimal('187390'))
        self.assertEqual(cartola.egresos, Decimal('83980'))
        self.assertEqual(cartola.saldo_inicial, Decimal('478527'))
        self.assertEqual(cartola.saldo_final, Decimal('581937'))

    def test_avisa_cuando_falta_una_fila(self):
        recortada = CARTOLA.replace(
            '06/Ago 8049936 PAGO WEBPAY EPARIS $44.990 $438.337\n', '')
        cartola = self.leer(recortada)
        self.assertFalse(cartola.cuadra)
        self.assertIn('movimientos', cartola.nota_cuadre)

    def test_rechaza_un_pdf_sin_detalle(self):
        with self.assertRaises(ErrorCartola):
            self.leer('CARTOLA CUENTARUT N° 20344444\nCuentaRUT\nSaldo Final $ 0')

    def test_no_se_lo_lleva_el_lector_generico_de_bancoestado(self):
        reconocen = [c for c, lector in BANCOS.items() if lector().reconoce(CARTOLA)]
        self.assertEqual(reconocen[0], 'estado_cuentarut')
