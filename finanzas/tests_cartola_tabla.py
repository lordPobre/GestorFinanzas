"""Tests del lector de cartolas exportadas (CSV y Excel) y del diagnóstico."""
import io
from decimal import Decimal

from django.test import SimpleTestCase

from .cartolas.base import ErrorCartola, muestra_anonima
from .cartolas.tabla import es_tabla, leer_tabla

CARGO_ABONO = """Cartola cuenta corriente Banco BCI
Fecha;Descripción;Cargo;Abono;Saldo
06/08/2026;TRANSFERENCIA DE JUAN CARVAJAL;;36790;515317
06/08/2026;PAGO WEBPAY EPARIS;44990;;470327
07/08/2026;DEP EN EFECTIVO;;147000;617327
"""

MONTO_Y_SALDO = """Fecha,Detalle,Monto,Saldo
2026-08-06,TRANSFERENCIA DE JUAN CARVAJAL,36790,515317
2026-08-06,PAGO WEBPAY EPARIS,44990,470327
2026-08-07,DEP EN EFECTIVO,147000,617327
"""

MONTO_CON_SIGNO = """Fecha\tDescripción\tMonto
06/08/2026\tCOMPRA SUPERMERCADO\t-44990
07/08/2026\tSUELDO\t980000
08/08/2026\tCOMISION MENSUAL\t-1490
"""

SIN_COLUMNAS = """Informe de gastos
Item;Responsable;Comentario
1;Ana;Nada que ver con una cartola
"""


def archivo(texto):
    return io.BytesIO(texto.encode('utf-8'))


class DeteccionTests(SimpleTestCase):

    def test_reconoce_las_extensiones_tabulares(self):
        for nombre in ('cartola.csv', 'CARTOLA.CSV', 'movs.xlsx', 'export.tsv'):
            self.assertTrue(es_tabla(nombre), nombre)

    def test_no_se_queda_con_los_pdf(self):
        self.assertFalse(es_tabla('cartola.pdf'))


class ColumnasCargoAbonoTests(SimpleTestCase):

    def setUp(self):
        self.cartola = leer_tabla(archivo(CARGO_ABONO), 'cartola.csv')

    def test_lee_las_tres_filas(self):
        self.assertEqual(len(self.cartola.movimientos), 3)

    def test_el_signo_viene_de_la_columna(self):
        por_desc = {m.descripcion: m for m in self.cartola.movimientos}
        self.assertEqual(por_desc['PAGO WEBPAY EPARIS'].tipo, 'EGRESO')
        self.assertEqual(por_desc['PAGO WEBPAY EPARIS'].monto, Decimal('44990'))
        self.assertEqual(por_desc['TRANSFERENCIA DE JUAN CARVAJAL'].tipo, 'INGRESO')

    def test_reconoce_el_banco_del_encabezado(self):
        self.assertIn('BCI', self.cartola.banco)

    def test_queda_cuadrada(self):
        self.assertTrue(self.cartola.cuadra, self.cartola.nota_cuadre)


class MontoYSaldoTests(SimpleTestCase):

    def test_el_signo_sale_de_la_cadena_de_saldos(self):
        cartola = leer_tabla(archivo(MONTO_Y_SALDO), 'movs.csv')
        por_desc = {m.descripcion: m for m in cartola.movimientos}
        self.assertEqual(por_desc['PAGO WEBPAY EPARIS'].tipo, 'EGRESO')
        self.assertEqual(por_desc['DEP EN EFECTIVO'].tipo, 'INGRESO')

    def test_deja_la_mas_nueva_primero(self):
        cartola = leer_tabla(archivo(MONTO_Y_SALDO), 'movs.csv')
        fechas = [m.fecha for m in cartola.movimientos]
        self.assertEqual(fechas, sorted(fechas, reverse=True))


class MontoConSignoTests(SimpleTestCase):

    def test_el_signo_del_numero_decide(self):
        cartola = leer_tabla(archivo(MONTO_CON_SIGNO), 'export.tsv')
        tipos = {m.descripcion: m.tipo for m in cartola.movimientos}
        self.assertEqual(tipos['COMPRA SUPERMERCADO'], 'EGRESO')
        self.assertEqual(tipos['SUELDO'], 'INGRESO')
        self.assertEqual(tipos['COMISION MENSUAL'], 'EGRESO')


class RechazoTests(SimpleTestCase):

    def test_se_niega_si_no_reconoce_las_columnas(self):
        with self.assertRaises(ErrorCartola):
            leer_tabla(archivo(SIN_COLUMNAS), 'gastos.csv')

    def test_se_niega_con_un_archivo_vacio(self):
        with self.assertRaises(ErrorCartola):
            leer_tabla(archivo(''), 'vacio.csv')


class MuestraAnonimaTests(SimpleTestCase):

    CRUDO = ('CARTOLA CUENTARUT N° 20344444\n'
             'CORTEZ GONZALEZ MARIA FERNANDA 16/09/2026 15:22\n'
             'Saldo Anterior $ 478.527\n'
             '06/Ago 8019968 TEF DE JUAN CARVAJAL $36.790 $515.317\n')

    def test_borra_nombres_y_cifras(self):
        muestra = muestra_anonima(self.CRUDO)
        self.assertNotIn('CORTEZ', muestra)
        self.assertNotIn('CARVAJAL', muestra)
        self.assertNotIn('20344444', muestra)
        self.assertNotIn('478.527', muestra)

    def test_conserva_la_estructura(self):
        muestra = muestra_anonima(self.CRUDO)
        self.assertIn('CARTOLA', muestra)
        self.assertIn('CUENTARUT', muestra)
        self.assertIn('Saldo Anterior $ 999.999', muestra)
        self.assertIn('99/Ago', muestra)
        self.assertIn('TEF', muestra)

    def test_no_se_pasa_del_tope_de_lineas(self):
        largo = '\n'.join(f'linea {i}' for i in range(200))
        self.assertLessEqual(len(muestra_anonima(largo).splitlines()), 45)
