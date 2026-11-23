import os
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from ..cartolas import lector_ia, leer_cartola
from ..cartolas.cuotas_conocidas import reconocer_cuotas
from ..models import Deuda, Persona, Prestamo

PAGINA = '\n'.join([
    'ESTADO DE CUENTA',
    'Fecha Facturación Estado de Cuenta: 19/11/2026',
    'Período Facturado 20/10/2026 19/11/2026',
    'S/I 02/06/2026 Falabella.com T 95.990 108.075 06/06 jul-2026 18.015',
    'Con Con 15/10/2026 1454-pinares concon A1 180.000 180.000 02/06 nov-2026 30.000',
    'Con Con 15/10/2026 1454-pinares concon A1 263.120 263.120 02/06 nov-2026 43.853',
    'Vina Del Mar 22/10/2026 Adm medica centromed T 180.000 180.000 01/03 dic-2026 60.000',
    'Vina Del Mar 22/10/2026 Adm medica centromed T 95.000 95.000 01/01 dic-2026 95.000',
    'Monto Total Facturado a Pagar 246.868',
])


def _fila(fecha, descripcion, monto, a=0, t=0):
    return {'fecha': fecha, 'descripcion': descripcion, 'monto': monto, 'sentido': 'cargo',
            'saldo': '', 'cuota_actual': a, 'cuota_total': t, 'es_pago_tarjeta': False}


def _respuesta(movimientos):
    datos = {'tipo_documento': 'tarjeta', 'institucion': 'Banco Falabella',
             'fecha_facturacion': '2026-11-19', 'saldo_inicial': '', 'saldo_final': '',
             'total_facturado': '246.868', 'movimientos': movimientos}
    return SimpleNamespace(content=[SimpleNamespace(type='tool_use', name='entregar_cartola', input=datos)],
                           usage=None, stop_reason='tool_use')


CON_EL_TOTAL_DE_LA_COMPRA = _respuesta([
    _fila('2026-06-02', 'Falabella.com', '108.075', 6, 6),
    _fila('2026-10-15', '1454-pinares concon', '180.000', 2, 6),
    _fila('2026-10-15', '1454-pinares concon', '263.120', 2, 6),
    _fila('2026-10-22', 'Adm medica centromed', '180.000', 1, 3),
    _fila('2026-10-22', 'Adm medica centromed', '95.000'),
])


class ValorDeLaCuotaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def _leer(self, *respuestas):
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'k'}), \
                mock.patch('anthropic.Anthropic') as cliente, \
                mock.patch.object(lector_ia, 'paginas_de_pdf', return_value=[PAGINA]):
            crear = cliente.return_value.messages.create
            crear.side_effect = list(respuestas)
            cartola = leer_cartola(BytesIO(b'%PDF-1.4'), '', 'estado.pdf', self.ana)
        return cartola, crear

    def _monto(self, cartola, texto, cuotas):
        return sorted(m.monto for m in cartola.movimientos
                      if texto in m.descripcion.lower() and m.cuota_total == cuotas)

    def test_si_la_ia_toma_el_total_de_la_compra_queda_el_valor_de_la_cuota(self):
        cartola, crear = self._leer(CON_EL_TOTAL_DE_LA_COMPRA)
        self.assertEqual(crear.call_count, 1)
        self.assertTrue(cartola.cuadra)
        self.assertEqual(self._monto(cartola, 'pinares', 6), [Decimal('30000'), Decimal('43853')])
        self.assertEqual(self._monto(cartola, 'centromed', 3), [Decimal('60000')])
        self.assertEqual(self._monto(cartola, 'falabella.com', 6), [Decimal('18015')])
        self.assertEqual(self._monto(cartola, 'centromed', 0), [Decimal('95000')])

    def test_las_cuotas_corregidas_se_unen_a_cuotas_y_a_me_deben(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Pinares Concón',
                                     monto_total=Decimal('180000'), cuotas_totales=6,
                                     fecha_inicio=date(2026, 11, 5))
        camila = Persona.objects.create(usuario=self.ana, nombre='Camila', lado='ME_DEBE')
        prestamo = Prestamo.objects.create(persona=camila, descripcion='Pinares Concón',
                                           monto=Decimal('263120'), tipo='CUOTAS', cuotas_totales=6,
                                           fecha=date(2026, 10, 15))
        cartola, _ = self._leer(CON_EL_TOTAL_DE_LA_COMPRA)
        reconocer_cuotas(cartola, self.ana)
        filas = {m.monto: m for m in cartola.movimientos if 'pinares' in m.descripcion.lower()}
        self.assertEqual(filas[Decimal('30000')].deuda_id, deuda.pk)
        self.assertEqual(filas[Decimal('43853')].prestamo_id, prestamo.pk)

    def test_si_la_ia_ya_trae_el_valor_de_la_cuota_no_cambia(self):
        bien = _respuesta([
            _fila('2026-06-02', 'Falabella.com', '18.015', 6, 6),
            _fila('2026-10-15', '1454-pinares concon', '30.000', 2, 6),
            _fila('2026-10-15', '1454-pinares concon', '43.853', 2, 6),
            _fila('2026-10-22', 'Adm medica centromed', '60.000', 1, 3),
            _fila('2026-10-22', 'Adm medica centromed', '95.000'),
        ])
        cartola, _ = self._leer(bien)
        self.assertTrue(cartola.cuadra)
        self.assertEqual(self._monto(cartola, 'pinares', 6), [Decimal('30000'), Decimal('43853')])
