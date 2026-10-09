from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..cartolas import BANCOS, enriquecer
from ..cartolas.ciclo import inicio_estimado, reubicar_anteriores
from ..models import Transaccion
from ..views.cartola import SESION

CMR = """ESTADO DE CUENTA TARJETA CMR
N° de Contrato: ****1234
Fecha Facturación: 19/09/2026
Monto Total Facturado a Pagar 79.970
SANTIAGO 25/08/2026 FALABELLA ONLINE T 45.990 45.990 01/01 sep-2026 45.990
SANTIAGO 05/09/2026 FARMACIA CRUZ VERDE T 12.990 12.990 01/01 oct-2026 12.990
S/I 10/07/2026 FALABELLA TV T 62.970 62.970 03/03 sep-2026 20.990
"""

POLAR = """ESTADO DE CUENTA TARJETA LA POLAR
Fecha de vencimiento: 05/10/2026
Monto total facturado a pagar 65.890
28/08/2026 FARMACIA AHUMADA 45.900
10/09/2026 SUPERMERCADO LIDER 19.990
"""


def _cmr(texto=CMR):
    return BANCOS['cmr']().parsear(texto)


def _buscar(cartola, inicio):
    return next(m for m in cartola.movimientos if m.descripcion.startswith(inicio))


class CicloTests(SimpleTestCase):

    def test_una_compra_despues_del_cierre_anterior_va_al_mes_del_ciclo(self):
        compra = _buscar(_cmr(), 'FALABELLA ONLINE')
        self.assertEqual(compra.fecha, date(2026, 9, 19))
        self.assertEqual(compra.fecha_compra, date(2026, 8, 25))
        self.assertIn('25/08/2026', compra.aviso)
        self.assertIn('septiembre', compra.aviso)

    def test_una_compra_del_mismo_mes_conserva_su_fecha(self):
        compra = _buscar(_cmr(), 'FARMACIA')
        self.assertEqual(compra.fecha, date(2026, 9, 5))
        self.assertIsNone(compra.fecha_compra)

    def test_el_periodo_muestra_el_ciclo(self):
        cartola = _cmr()
        self.assertEqual(cartola.periodo, 'Septiembre 2026 · ciclo del 20/08 al 19/09')
        self.assertTrue(cartola.cuadra, cartola.nota_cuadre)

    def test_el_periodo_facturado_del_estado_manda(self):
        texto = CMR.replace('Fecha Facturación: 19/09/2026',
                            'Período Facturado Desde: 21/08/2026 Hasta: 20/09/2026')
        cartola = _cmr(texto)
        self.assertEqual(cartola.periodo, 'Septiembre 2026 · ciclo del 21/08 al 20/09')
        self.assertEqual(_buscar(cartola, 'FALABELLA TV').fecha, date(2026, 9, 20))
        self.assertEqual(_buscar(cartola, 'FALABELLA ONLINE').fecha, date(2026, 9, 20))

    def test_el_inicio_del_ciclo_se_ajusta_a_meses_cortos(self):
        self.assertEqual(inicio_estimado(date(2026, 9, 19)), date(2026, 8, 20))
        self.assertEqual(inicio_estimado(date(2026, 3, 31)), date(2026, 3, 1))

    def test_la_fecha_de_vencimiento_no_se_toma_como_cierre(self):
        cartola = BANCOS['la_polar']().parsear(POLAR)
        compra = _buscar(cartola, 'FARMACIA')
        self.assertEqual(compra.fecha, date(2026, 8, 28))
        self.assertIsNone(compra.fecha_compra)

    def test_una_casa_comercial_con_fecha_de_facturacion_tambien_usa_el_ciclo(self):
        texto = POLAR.replace('Fecha de vencimiento: 05/10/2026', 'Fecha de facturación: 19/09/2026')
        cartola = BANCOS['la_polar']().parsear(texto)
        compra = _buscar(cartola, 'FARMACIA')
        self.assertEqual(compra.fecha, date(2026, 9, 19))
        self.assertEqual(compra.fecha_compra, date(2026, 8, 28))
        self.assertEqual(_buscar(cartola, 'SUPERMERCADO').fecha, date(2026, 9, 10))


class ReubicarTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def test_una_compra_anotada_en_el_mes_equivocado_se_propone_mover(self):
        vieja = Transaccion.objects.create(
            usuario=self.ana, tipo='EGRESO', monto=Decimal('45990'), categoria='Compras',
            fecha=date(2026, 8, 25), descripcion='FALABELLA ONLINE (SANTIAGO)',
        )
        cartola = _cmr()
        enriquecer(cartola, self.ana)
        reubicar_anteriores(cartola, self.ana)
        compra = _buscar(cartola, 'FALABELLA ONLINE')
        self.assertEqual(compra.mover_id, vieja.pk)
        self.assertFalse(compra.ya_existe)
        self.assertIn('se mueve a septiembre', compra.aviso)

    def test_confirmar_mueve_la_anterior_en_vez_de_duplicarla(self):
        vieja = Transaccion.objects.create(
            usuario=self.ana, tipo='EGRESO', monto=Decimal('45990'), categoria='Compras',
            fecha=date(2026, 8, 25), descripcion='Mi compra online',
        )
        self.client.force_login(self.ana)
        sesion = self.client.session
        sesion[SESION] = {
            'banco': 'CMR / Banco Falabella', 'periodo': 'Septiembre 2026', 'cuenta': '',
            'cuadra': True, 'descuadre': '0', 'nota_cuadre': '', 'saldo_inicial': '',
            'saldo_final': '',
            'movimientos': [{
                'fecha': '2026-09-19', 'descripcion': 'FALABELLA ONLINE (SANTIAGO)',
                'monto': '45990', 'tipo': 'EGRESO', 'categoria': 'Compras',
                'cuota_actual': 0, 'cuota_total': 0, 'es_suscripcion': False,
                'ya_existe': False, 'aviso': '', 'fecha_compra': '2026-08-25',
                'mover_id': vieja.pk,
            }],
        }
        sesion.save()
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1'})
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)
        vieja.refresh_from_db()
        self.assertEqual(vieja.fecha, date(2026, 9, 19))
        self.assertEqual(vieja.descripcion, 'Mi compra online')

    def test_no_mueve_movimientos_de_otra_persona(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        ajena = Transaccion.objects.create(
            usuario=bruno, tipo='EGRESO', monto=Decimal('45990'),
            fecha=date(2026, 8, 25), descripcion='FALABELLA ONLINE (SANTIAGO)',
        )
        cartola = _cmr()
        reubicar_anteriores(cartola, self.ana)
        self.assertIsNone(_buscar(cartola, 'FALABELLA ONLINE').mover_id)
        ajena.refresh_from_db()
        self.assertEqual(ajena.fecha, date(2026, 8, 25))
