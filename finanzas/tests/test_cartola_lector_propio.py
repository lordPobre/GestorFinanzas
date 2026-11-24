import os
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from ..cartolas import BANCOS, lector_ia, leer_cartola
from ..cartolas.base import Cartola, MovimientoLeido
from ..cartolas.cuotas_conocidas import reconocer_cuotas
from ..models import Contador, Deuda, Persona, Prestamo

FILAS = [
    'S/I 02/06/2026 Falabella.com T 95.990 108.075 06/06 jul-2026 18.015',
    'Vina Del Mar 14/09/2026 Diagnostico imagenes T 54.990 60.089 02/03 nov-2026 20.029',
    'Con Con 15/10/2026 1454-pinares concon A1 180.000 180.000 02/06 nov-2026 30.000',
    'Con Con 15/10/2026 1454-pinares concon A1 263.120 263.120 02/06 nov-2026 43.853',
    'Vina Del Mar 22/10/2026 Adm medica centromed T 180.000 180.000 01/03 dic-2026 60.000',
    'Las Condes 05/11/2026 Merpago*mercadolibre A1 30.503 30.503 01/01 dic-2026 30.503',
    'Las Condes 09/11/2026 Merpago*mercadolibre A1 -17.513 -17.513 01/01 -17.513',
    'London 08/11/2026 Airbnb * hmx T 74.615 74.615 01/01 dic-2026 74.615',
    'London 15/11/2026 Airbnb * hmx T -74.615 -74.615 01/01 -74.615',
]
PAGO = 'S/I 28/10/2026 Pago tarjeta cmr T -2.471.960 0 01/01'
CABEZA = ['ESTADO DE CUENTA', 'Fecha Facturación Estado de Cuenta: 19/11/2026',
          'Período Facturado 20/10/2026 19/11/2026']
PIE = ['Monto Total Facturado a Pagar 184.887']
FALABELLA = '\n'.join(CABEZA + ['Paga tu Estado de Cuenta en tu App BancoFalabella'] + FILAS + [PAGO] + PIE)
SIN_MARCA = '\n'.join(CABEZA + FILAS + PIE)


def _fila(fecha, descripcion, monto, a=0, t=0):
    return {'fecha': fecha, 'descripcion': descripcion, 'monto': monto, 'sentido': 'cargo',
            'saldo': '', 'cuota_actual': a, 'cuota_total': t, 'es_pago_tarjeta': False}


LEIDA_POR_LA_IA = SimpleNamespace(content=[SimpleNamespace(type='tool_use', name='entregar_cartola', input={
    'tipo_documento': 'tarjeta', 'institucion': 'Banco Falabella', 'fecha_facturacion': '2026-11-19',
    'saldo_inicial': '', 'saldo_final': '', 'total_facturado': '184.887',
    'movimientos': [
        _fila('2026-06-02', 'Falabella.com', '95.990', 6, 6),
        _fila('2026-09-14', 'Diagnostico imagenes', '54.990', 2, 3),
        _fila('2026-10-15', '1454-pinares concon', '180.000', 2, 6),
        _fila('2026-10-15', '1454-pinares concon', '263.120', 2, 6),
        _fila('2026-10-22', 'Adm medica centromed', '180.000', 1, 3),
        _fila('2026-11-05', 'Merpago*mercadolibre', '30.503'),
        _fila('2026-11-09', 'Merpago*mercadolibre', '-17.513'),
        _fila('2026-11-08', 'Airbnb * hmx', '74.615'),
        _fila('2026-11-15', 'Airbnb * hmx', '-74.615'),
    ]})], usage=None, stop_reason='tool_use')


def _montos(cartola, texto, tipo='EGRESO'):
    return sorted(m.monto for m in cartola.movimientos if texto in m.descripcion.lower() and m.tipo == tipo)


class LectorFalabellaTests(SimpleTestCase):

    def test_las_devoluciones_se_restan_y_el_estado_cuadra(self):
        cartola = BANCOS['cmr']().parsear(FALABELLA)
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)
        self.assertEqual(cartola.descuadre, 0)
        devoluciones = sorted(m.monto for m in cartola.movimientos if m.tipo == 'INGRESO')
        self.assertEqual(devoluciones, [Decimal('17513'), Decimal('74615')])
        pago = next(m for m in cartola.movimientos if 'pago tarjeta' in m.descripcion.lower())
        self.assertIn('No es un gasto', pago.aviso)

    def test_la_cuota_guarda_el_precio_y_el_total_de_la_compra(self):
        cartola = BANCOS['cmr']().parsear(FALABELLA)
        examen = next(m for m in cartola.movimientos if 'diagnostico' in m.descripcion.lower())
        self.assertEqual(examen.monto, Decimal('20029'))
        self.assertEqual(examen.montos_compra, (Decimal('54990'), Decimal('60089')))


class LecturaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def _leer(self, texto, *respuestas):
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'k'}), \
                mock.patch('anthropic.Anthropic') as cliente, \
                mock.patch.object(lector_ia, 'paginas_de_pdf', return_value=[texto]):
            crear = cliente.return_value.messages.create
            crear.side_effect = list(respuestas)
            cartola = leer_cartola(BytesIO(b'%PDF-1.4'), '', 'estado.pdf', self.ana)
        return cartola, crear

    def test_si_el_lector_propio_cuadra_no_se_usa_la_ia(self):
        cartola, crear = self._leer(FALABELLA)
        self.assertEqual(crear.call_count, 0)
        self.assertFalse(Contador.objects.filter(clave__startswith=f'cartola-ia:{self.ana.pk}:').exists())
        self.assertTrue(cartola.cuadra)
        self.assertEqual(_montos(cartola, 'pinares'), [Decimal('30000'), Decimal('43853')])
        self.assertEqual(_montos(cartola, 'centromed'), [Decimal('60000')])

    def test_la_ia_resta_las_devoluciones_y_deja_el_valor_de_la_cuota(self):
        cartola, crear = self._leer(SIN_MARCA, LEIDA_POR_LA_IA)
        self.assertEqual(crear.call_count, 1)
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)
        self.assertEqual(_montos(cartola, 'airbnb', 'INGRESO'), [Decimal('74615')])
        self.assertEqual(_montos(cartola, 'mercadolibre', 'INGRESO'), [Decimal('17513')])
        self.assertEqual(_montos(cartola, 'diagnostico'), [Decimal('20029')])
        self.assertEqual(_montos(cartola, 'falabella.com'), [Decimal('18015')])

    def test_lo_que_te_deben_anotado_con_el_precio_se_une_aunque_la_cuota_traiga_interes(self):
        camila = Persona.objects.create(usuario=self.ana, nombre='Camila', lado='ME_DEBE')
        examen = Prestamo.objects.create(persona=camila, descripcion='Diagnóstico imágenes',
                                         monto=Decimal('54990'), tipo='CUOTAS', cuotas_totales=3,
                                         fecha=date(2026, 9, 14))
        cartola, _ = self._leer(FALABELLA)
        reconocer_cuotas(cartola, self.ana)
        fila = next(m for m in cartola.movimientos if 'diagnostico' in m.descripcion.lower())
        self.assertEqual((fila.monto, fila.prestamo_id), (Decimal('20029'), examen.pk))
        self.assertTrue(fila.vinculo_seguro)

    def test_una_compra_de_cuotas_anotada_con_el_precio_se_marca_pagada(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Diagnóstico imágenes',
                                     monto_total=Decimal('54990'), cuotas_totales=3,
                                     fecha_inicio=date(2026, 10, 5))
        cartola, _ = self._leer(FALABELLA)
        reconocer_cuotas(cartola, self.ana)
        fila = next(m for m in cartola.movimientos if 'diagnostico' in m.descripcion.lower())
        self.assertEqual((fila.deuda_id, fila.deuda_periodo), (deuda.pk, 202611))
        self.assertTrue(fila.vinculo_seguro)

    def test_la_cuota_con_el_nombre_gana_aunque_venga_despues(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('62970'),
                                     cuotas_totales=3, fecha_inicio=date(2026, 7, 19))

        def cuota(descripcion):
            return MovimientoLeido(fecha=date(2026, 9, 19), descripcion=descripcion, monto=Decimal('20990'),
                                   tipo='EGRESO', saldo=Decimal(0), cuota_actual=3, cuota_total=3)

        otra, buena = cuota('XYZ · cuota 3 de 3'), cuota('NOTEBOOK LENOVO · cuota 3 de 3')
        reconocer_cuotas(Cartola(banco='CMR / Banco Falabella', movimientos=[otra, buena]), self.ana)
        self.assertEqual((otra.deuda_id, buena.deuda_id), (None, deuda.pk))
        self.assertTrue(buena.vinculo_seguro)
