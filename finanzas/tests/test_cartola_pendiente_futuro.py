from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..cartolas.base import MovimientoLeido
from ..models import Transaccion
from ..servicios.repetidos import marcar_repetidas
from ..views.cartola import SESION


def _leido(descripcion, fecha=date(2026, 10, 20), monto='39990'):
    return MovimientoLeido(fecha=fecha, descripcion=descripcion, monto=Decimal(monto),
                           tipo='EGRESO', saldo=Decimal('0'))


class PendienteFuturoEnLaCartola(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def _gasto(self, descripcion, fecha=date(2026, 11, 5), pagado=False):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('39990'),
                                          categoria='Comida', fecha=fecha, descripcion=descripcion,
                                          pagado=pagado)

    def _marcar(self, *movs):
        cartola = SimpleNamespace(movimientos=list(movs))
        marcar_repetidas(cartola, self.ana)
        return cartola.movimientos

    def test_reconoce_el_pendiente_del_mes_siguiente_aunque_la_descripcion_no_calce(self):
        t = self._gasto('Zapatillas')
        m, = self._marcar(_leido('FALABELLA PARQUE ARAUCO'))
        self.assertEqual(m.reemplaza_id, t.pk)
        self.assertFalse(m.reemplaza_seguro)
        self.assertIn('pendiente para el 05/11', m.aviso)

    def test_con_la_misma_descripcion_queda_marcado_para_reemplazar(self):
        t = self._gasto('Zapatillas')
        m, = self._marcar(_leido('ZAPATILLAS'))
        self.assertEqual(m.reemplaza_id, t.pk)
        self.assertTrue(m.reemplaza_seguro)
        self.assertIn('sigue por pagar', m.aviso)

    def test_un_gasto_futuro_ya_pagado_o_muy_lejano_no_se_toca(self):
        self._gasto('Zapatillas', pagado=True)
        self._gasto('Zapatillas', fecha=date(2027, 1, 30))
        m, = self._marcar(_leido('ZAPATILLAS'))
        self.assertIsNone(m.reemplaza_id)

    def test_al_reemplazarlo_conserva_su_fecha_y_sigue_por_pagar(self):
        t = self._gasto('Zapatillas')
        self.client.force_login(self.ana)
        sesion = self.client.session
        sesion[SESION] = {
            'banco': 'Banco de Chile', 'periodo': 'Octubre 2026', 'cuenta': '', 'cuadra': True,
            'descuadre': '0', 'nota_cuadre': '', 'saldo_inicial': '', 'saldo_final': '',
            'movimientos': [{
                'fecha': '2026-10-20', 'descripcion': 'FALABELLA PARQUE ARAUCO', 'monto': '39990',
                'tipo': 'EGRESO', 'categoria': 'Otros', 'cuota_actual': 0, 'cuota_total': 0,
                'es_suscripcion': False, 'ya_existe': False, 'aviso': '', 'reemplaza_id': t.pk,
            }],
        }
        sesion.save()
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'reemplazar_0': '1'})
        t.refresh_from_db()
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)
        self.assertEqual(t.fecha, date(2026, 11, 5))
        self.assertFalse(t.pagado)
        self.assertEqual(t.descripcion, 'FALABELLA PARQUE ARAUCO')
