from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..cartolas.base import Cartola, MovimientoLeido
from ..cartolas.cuotas_conocidas import reconocer_cuotas
from ..models import Deuda, PagoCuota, Persona, Prestamo, Transaccion
from ..servicios.repetidos import marcar_repetidas
from ..views.cartola import SESION


def _cuota(fecha, descripcion, monto, actual, total):
    return MovimientoLeido(fecha=fecha, descripcion=descripcion, monto=Decimal(monto), tipo='EGRESO',
                           saldo=Decimal(0), categoria='Compras', cuota_actual=actual, cuota_total=total)


def _cartola(*movs):
    return Cartola(banco='CMR / Banco Falabella', movimientos=list(movs))


class _Base(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def compra(self, usuario=None, **datos):
        valores = {'usuario': usuario or self.ana, 'acreedor': 'Falabella TV',
                   'monto_total': Decimal('62970'), 'cuotas_totales': 3,
                   'fecha_inicio': date(2026, 7, 19)}
        valores.update(datos)
        return Deuda.objects.create(**valores)

    def prestamo(self, usuario=None, **datos):
        quien, _ = Persona.objects.get_or_create(usuario=usuario or self.ana, nombre='Camila',
                                                 lado='ME_DEBE')
        valores = {'persona': quien, 'descripcion': 'Zapatillas Paris', 'monto': Decimal('60000'),
                   'tipo': 'CUOTAS', 'cuotas_totales': 3, 'fecha': date(2026, 8, 10)}
        valores.update(datos)
        return Prestamo.objects.create(**valores)

    def pago_en_la_app(self, deuda):
        tx = Transaccion.objects.create(
            usuario=self.ana, tipo='EGRESO', monto=Decimal('20990'), categoria='Compras',
            descripcion='Cuota 3/3 — Falabella TV', fecha=date(2026, 9, 19), es_cuota=True,
            origen=Transaccion.CUOTA)
        PagoCuota.objects.create(deuda=deuda, periodo=202609, monto=Decimal('20990'),
                                 fecha_pago=date(2026, 9, 20), transaccion=tx)
        return tx


class ReconocerTests(_Base):

    def test_una_cuota_de_una_compra_anotada_a_mano_se_une_a_esa_compra(self):
        deuda = self.compra(categoria='Tecnologia')
        cartola = _cartola(_cuota(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 3', '20990', 3, 3))
        reconocer_cuotas(cartola, self.ana)
        fila = cartola.movimientos[0]
        self.assertEqual((fila.deuda_id, fila.deuda_periodo), (deuda.pk, 202609))
        self.assertTrue(fila.vinculo_seguro)
        self.assertEqual(fila.categoria, 'Tecnologia')
        self.assertIn('septiembre 2026', fila.deuda_texto)

    def test_una_compra_creada_desde_otra_cartola_sigue_la_numeracion_del_banco(self):
        deuda = self.compra(monto_total=Decimal('41980'), cuotas_totales=2,
                            fecha_inicio=date(2026, 8, 19))
        cartola = _cartola(_cuota(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 3', '20990', 3, 3))
        reconocer_cuotas(cartola, self.ana)
        fila = cartola.movimientos[0]
        self.assertEqual((fila.deuda_id, fila.deuda_periodo), (deuda.pk, 202609))

    def test_otro_monto_u_otra_cantidad_de_cuotas_no_se_une(self):
        self.compra()
        cartola = _cartola(_cuota(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 3', '35990', 3, 3),
                           _cuota(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 6', '20990', 3, 6))
        reconocer_cuotas(cartola, self.ana)
        self.assertEqual([m.deuda_id for m in cartola.movimientos], [None, None])

    def test_entre_dos_compras_iguales_gana_la_del_nombre(self):
        self.compra(acreedor='Notebook')
        tele = self.compra()
        cartola = _cartola(_cuota(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 3', '20990', 3, 3))
        reconocer_cuotas(cartola, self.ana)
        self.assertEqual(cartola.movimientos[0].deuda_id, tele.pk)

    def test_sin_el_nombre_y_con_dos_posibles_queda_sin_marcar(self):
        self.compra(acreedor='Notebook')
        self.compra(acreedor='Bicicleta')
        cartola = _cartola(_cuota(date(2026, 9, 19), 'XYZ 03/03', '20990', 3, 3))
        reconocer_cuotas(cartola, self.ana)
        fila = cartola.movimientos[0]
        self.assertIsNotNone(fila.deuda_id)
        self.assertFalse(fila.vinculo_seguro)

    def test_si_la_cuota_ya_se_pago_en_la_app_se_propone_reemplazar_ese_pago(self):
        tx = self.pago_en_la_app(self.compra())
        cartola = _cartola(_cuota(date(2026, 9, 25), 'FALABELLA TV · cuota 3 de 3', '20990', 3, 3))
        reconocer_cuotas(cartola, self.ana)
        marcar_repetidas(cartola, self.ana)
        fila = cartola.movimientos[0]
        self.assertEqual((fila.reemplaza_id, fila.reemplaza_seguro, fila.deuda_id), (tx.pk, True, None))
        self.assertIn('Ya pagaste la cuota de septiembre 2026', fila.aviso)

    def test_una_cuota_de_algo_que_te_deben_se_reconoce(self):
        prestamo = self.prestamo()
        cartola = _cartola(_cuota(date(2026, 9, 19), 'PARIS ZAPATILLAS 02/03', '20000', 2, 3))
        reconocer_cuotas(cartola, self.ana)
        fila = cartola.movimientos[0]
        self.assertEqual((fila.prestamo_id, fila.deuda_id), (prestamo.pk, None))
        self.assertTrue(fila.vinculo_seguro)
        self.assertIn('Camila', fila.prestamo_texto)

    def test_no_se_une_a_compras_de_otra_cuenta(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        self.compra(usuario=bruno)
        self.prestamo(usuario=bruno, descripcion='Falabella TV', monto=Decimal('62970'),
                      fecha=date(2026, 7, 19))
        cartola = _cartola(_cuota(date(2026, 9, 19), 'FALABELLA TV · cuota 3 de 3', '20990', 3, 3))
        reconocer_cuotas(cartola, self.ana)
        fila = cartola.movimientos[0]
        self.assertEqual((fila.deuda_id, fila.prestamo_id), (None, None))


class ConfirmarTests(_Base):

    def revisar(self, **extra):
        fila = {'fecha': '2026-09-19', 'descripcion': 'FALABELLA TV · cuota 3 de 3', 'monto': '20990',
                'tipo': 'EGRESO', 'categoria': 'Compras', 'cuota_actual': 3, 'cuota_total': 3,
                'es_suscripcion': False, 'ya_existe': False, 'aviso': ''}
        fila.update(extra)
        self.client.force_login(self.ana)
        sesion = self.client.session
        sesion[SESION] = {'banco': 'CMR / Banco Falabella', 'periodo': '', 'cuenta': '', 'cuadra': True,
                          'descuadre': '0', 'nota_cuadre': '', 'saldo_inicial': '', 'saldo_final': '',
                          'movimientos': [fila]}
        sesion.save()

    def test_marca_pagada_la_cuota_en_vez_de_crear_otra_compra(self):
        deuda = self.compra()
        self.revisar(deuda_id=deuda.pk, deuda_periodo=202609, vinculo_seguro=True)
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'cuota_0': '1', 'deuda_0': '1'})
        self.assertEqual(Deuda.objects.filter(usuario=self.ana).count(), 1)
        pago = PagoCuota.objects.get(deuda=deuda)
        self.assertEqual((pago.periodo, pago.monto, pago.fecha_pago),
                         (202609, Decimal('20990'), date(2026, 9, 19)))
        self.assertEqual(pago.transaccion.origen, Transaccion.CARTOLA)
        self.assertTrue(pago.transaccion.es_cuota)
        deuda.refresh_from_db()
        self.assertEqual(deuda.cuotas_pagadas, 1)
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)

    def test_si_ya_estaba_pagada_en_la_app_no_queda_doble(self):
        deuda = self.compra()
        tx = self.pago_en_la_app(deuda)
        self.revisar(deuda_id=deuda.pk, deuda_periodo=202609, vinculo_seguro=True)
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'cuota_0': '1'})
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)
        self.assertEqual(PagoCuota.objects.filter(deuda=deuda).count(), 1)
        tx.refresh_from_db()
        self.assertEqual(tx.descripcion, 'FALABELLA TV · cuota 3 de 3')

    def test_una_cuota_anotada_suelta_se_reemplaza_y_queda_como_pago(self):
        deuda = self.compra()
        suelta = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('20990'),
                                            categoria='Compras', descripcion='Cuota tele',
                                            fecha=date(2026, 9, 18))
        self.revisar(deuda_id=deuda.pk, deuda_periodo=202609, vinculo_seguro=True,
                     reemplaza_id=suelta.pk, reemplaza_seguro=True)
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'cuota_0': '1', 'reemplazar_0': '1'})
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)
        self.assertEqual(PagoCuota.objects.get(deuda=deuda).transaccion, suelta)
        suelta.refresh_from_db()
        self.assertTrue(suelta.es_cuota)

    def test_una_cuota_que_te_deben_no_crea_otro_prestamo(self):
        prestamo = self.prestamo()
        self.revisar(descripcion='PARIS ZAPATILLAS 02/03', monto='20000', cuota_actual=2,
                     prestamo_id=prestamo.pk, vinculo_seguro=True)
        self.client.post(reverse('confirmar_cartola'), {
            'sel_0': '1', 'prestamo_0': '1', 'deben_0': '1', 'deben_persona_0': str(prestamo.persona_id)})
        self.assertEqual(Prestamo.objects.filter(persona__usuario=self.ana).count(), 1)
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)

    def test_sin_marcar_la_union_se_puede_crear_la_compra_como_antes(self):
        deuda = self.compra()
        self.revisar(deuda_id=deuda.pk, deuda_periodo=202609)
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'deuda_0': '1'})
        self.assertEqual(Deuda.objects.filter(usuario=self.ana).count(), 2)
        self.assertFalse(PagoCuota.objects.filter(deuda=deuda).exists())

    def test_no_paga_cuotas_de_otra_cuenta(self):
        bruno = User.objects.create_user('bruno', 'bruno@ejemplo.cl', 'clave-larga-2')
        ajena = self.compra(usuario=bruno)
        self.revisar(deuda_id=ajena.pk, deuda_periodo=202609, vinculo_seguro=True)
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'cuota_0': '1'})
        self.assertFalse(PagoCuota.objects.filter(deuda=ajena).exists())
        self.assertEqual(Transaccion.objects.filter(usuario=self.ana).count(), 1)

    def test_la_revision_muestra_la_union_y_esconde_crear_otra(self):
        deuda = self.compra()
        self.revisar(deuda_id=deuda.pk, deuda_periodo=202609, vinculo_seguro=True,
                     deuda_texto='Es «Falabella TV» de Cuotas · marcar pagada la de septiembre 2026')
        r = self.client.get(reverse('revisar_cartola'))
        self.assertContains(r, 'name="cuota_0" data-vinculo checked')
        self.assertContains(r, '<div data-sin-vinculo>', count=2)
        self.assertEqual(r.context['conocidas'], 1)
