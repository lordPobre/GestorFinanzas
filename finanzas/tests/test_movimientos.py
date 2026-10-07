from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Deuda, GastoPendiente, PagoCuota, Transaccion, UserProfile

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def _mensajes(respuesta):
    return [str(m) for m in get_messages(respuesta.wsgi_request)]


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.create(usuario=self.ana)
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        UserProfile.objects.create(usuario=self.beto)
        self.hoy = timezone.localdate()
        self.client.force_login(self.ana)

    def gasto(self, usuario=None, **extra):
        datos = {'usuario': usuario or self.ana, 'tipo': 'EGRESO', 'monto': Decimal('15000'),
                 'categoria': 'Comida', 'fecha': self.hoy, 'descripcion': 'Feria'}
        datos.update(extra)
        return Transaccion.objects.create(**datos)

    def formulario(self, **extra):
        datos = {'tipo': 'EGRESO', 'monto': '15000', 'categoria': 'Comida',
                 'descripcion': 'Feria', 'fecha': self.hoy.isoformat()}
        datos.update(extra)
        return datos


class RegistrarMovimiento(Base):
    def test_sin_sesion_pide_entrar(self):
        self.client.logout()
        respuesta = self.client.get(reverse('registrar_transaccion'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

    def test_la_pantalla_abre_con_el_tipo_pedido(self):
        self.assertEqual(self.client.get(reverse('registrar_transaccion')).context['tipo_inicial'],
                         'INGRESO')
        respuesta = self.client.get(reverse('registrar_transaccion') + '?tipo=EGRESO')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['tipo_inicial'], 'EGRESO')

    def test_un_gasto_queda_pagado_el_mismo_dia(self):
        respuesta = self.client.post(reverse('registrar_transaccion'), self.formulario())
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)
        t = Transaccion.objects.get(usuario=self.ana)
        self.assertTrue(t.pagado)
        self.assertEqual(t.fecha_pago, self.hoy)
        self.assertEqual(t.monto, Decimal('15000'))
        self.assertIn('Gasto registrado.', _mensajes(respuesta))

    def test_un_gasto_sin_pagar_queda_pendiente(self):
        respuesta = self.client.post(reverse('registrar_transaccion'), self.formulario(sin_pagar='1'))
        t = Transaccion.objects.get(usuario=self.ana)
        self.assertFalse(t.pagado)
        self.assertIsNone(t.fecha_pago)
        self.assertIn('Gasto anotado como pendiente de pago.', _mensajes(respuesta))

    def test_un_ingreso_nunca_queda_pendiente(self):
        respuesta = self.client.post(reverse('registrar_transaccion'), self.formulario(
            tipo='INGRESO', categoria='Sueldo', es_pendiente='1'))
        t = Transaccion.objects.get(usuario=self.ana)
        self.assertTrue(t.pagado)
        self.assertIn('Ingreso registrado.', _mensajes(respuesta))

    def test_vuelve_a_la_pantalla_desde_donde_se_anoto(self):
        respuesta = self.client.post(reverse('registrar_transaccion'),
                                     self.formulario(next=reverse('deudas')))
        self.assertRedirects(respuesta, reverse('deudas'), fetch_redirect_response=False)

    def test_un_next_a_otro_sitio_vuelve_al_inicio(self):
        respuesta = self.client.post(reverse('registrar_transaccion'),
                                     self.formulario(next='https://malo.example/'))
        self.assertRedirects(respuesta, reverse('dashboard'), fetch_redirect_response=False)

    def test_sin_monto_muestra_el_error_y_no_guarda(self):
        respuesta = self.client.post(reverse('registrar_transaccion'), self.formulario(monto='0'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Transaccion.objects.exists())
        self.assertTrue(any(m.startswith('Monto:') for m in _mensajes(respuesta)))

    def test_desde_el_panel_un_error_vuelve_a_la_pantalla(self):
        respuesta = self.client.post(reverse('registrar_transaccion'),
                                     self.formulario(monto='0', next=reverse('metas')))
        self.assertRedirects(respuesta, reverse('metas'), fetch_redirect_response=False)
        self.assertFalse(Transaccion.objects.exists())

    def test_un_gasto_no_se_anota_en_el_futuro(self):
        manana = (self.hoy + timedelta(days=1)).isoformat()
        self.client.post(reverse('registrar_transaccion'), self.formulario(fecha=manana))
        self.assertFalse(Transaccion.objects.exists())

    def test_un_ingreso_si_puede_ir_a_futuro(self):
        manana = (self.hoy + timedelta(days=1)).isoformat()
        self.client.post(reverse('registrar_transaccion'),
                         self.formulario(tipo='INGRESO', categoria='Sueldo', fecha=manana))
        self.assertTrue(Transaccion.objects.filter(usuario=self.ana, tipo='INGRESO').exists())

    def test_un_gasto_con_categoria_de_ingreso_no_se_guarda(self):
        self.client.post(reverse('registrar_transaccion'), self.formulario(categoria='Sueldo'))
        self.assertFalse(Transaccion.objects.exists())

    def test_nuevo_ingreso_abre_el_formulario_en_ingreso(self):
        respuesta = self.client.get(reverse('registrar_ingreso'))
        self.assertEqual(respuesta['Location'], reverse('registrar_transaccion') + '?tipo=INGRESO')


class EditarMovimiento(Base):
    def test_la_pantalla_carga_con_el_estado_de_pago(self):
        t = self.gasto(pagado=False)
        respuesta = self.client.get(reverse('editar_transaccion', args=[t.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['pendiente_inicial'])
        self.assertTrue(respuesta.context['editar'])

    def test_no_se_edita_un_movimiento_ajeno(self):
        t = self.gasto(usuario=self.beto)
        self.assertEqual(self.client.get(reverse('editar_transaccion', args=[t.pk])).status_code, 404)
        self.client.post(reverse('editar_transaccion', args=[t.pk]), self.formulario(monto='1'))
        t.refresh_from_db()
        self.assertEqual(t.monto, Decimal('15000'))

    def test_una_cuota_se_cambia_desde_cuotas(self):
        t = self.gasto(es_cuota=True)
        respuesta = self.client.get(reverse('editar_transaccion', args=[t.pk]))
        self.assertRedirects(respuesta, reverse('deudas'), fetch_redirect_response=False)

    def test_cambiar_el_monto_actualiza_el_gasto_pendiente(self):
        t = self.gasto(pagado=False)
        pendiente = GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('15000'),
                                                  fecha_vencimiento=self.hoy, transaccion=t)
        self.client.post(reverse('editar_transaccion', args=[t.pk]), self.formulario(monto='18000'))
        t.refresh_from_db()
        pendiente.refresh_from_db()
        self.assertEqual(t.monto, Decimal('18000'))
        self.assertTrue(t.pagado)
        self.assertEqual(t.fecha_pago, self.hoy)
        self.assertEqual(pendiente.monto, Decimal('18000'))
        self.assertTrue(pendiente.pagado)

    def test_marcarlo_pendiente_le_quita_la_fecha_de_pago(self):
        t = self.gasto(fecha_pago=self.hoy)
        self.client.post(reverse('editar_transaccion', args=[t.pk]), self.formulario(es_pendiente='1'))
        t.refresh_from_db()
        self.assertFalse(t.pagado)
        self.assertIsNone(t.fecha_pago)

    def test_un_gasto_ya_pagado_conserva_su_fecha_de_pago(self):
        ayer = self.hoy - timedelta(days=1)
        t = self.gasto(fecha=ayer, fecha_pago=self.hoy)
        self.client.post(reverse('editar_transaccion', args=[t.pk]),
                         self.formulario(fecha=ayer.isoformat(), descripcion='Feria del sábado'))
        t.refresh_from_db()
        self.assertEqual(t.descripcion, 'Feria del sábado')
        self.assertEqual(t.fecha_pago, self.hoy)


class EliminarMovimiento(Base):
    def test_borra_el_movimiento_y_su_gasto_pendiente(self):
        t = self.gasto()
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('15000'),
                                      fecha_vencimiento=self.hoy, transaccion=t)
        respuesta = self.client.post(reverse('eliminar_transaccion', args=[t.pk]))
        self.assertFalse(Transaccion.objects.exists())
        self.assertFalse(GastoPendiente.objects.exists())
        self.assertIn('Movimiento eliminado.', _mensajes(respuesta))

    def test_borrar_el_pago_de_una_cuota_la_deja_por_pagar(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('300000'),
                                     cuotas_totales=3, fecha_inicio=date(2026, 1, 10))
        t = self.gasto(es_cuota=True, monto=Decimal('100000'), descripcion='Cuota 1/3 Tienda')
        PagoCuota.objects.create(deuda=deuda, periodo=202601, monto=Decimal('100000'), transaccion=t)
        respuesta = self.client.post(reverse('eliminar_transaccion', args=[t.pk]))
        self.assertFalse(PagoCuota.objects.filter(deuda=deuda).exists())
        self.assertFalse(Transaccion.objects.filter(pk=t.pk).exists())
        deuda.refresh_from_db()
        self.assertEqual(deuda.cuotas_pagadas, 0)
        self.assertIn('Pago de la cuota anulado. Vuelve a quedar por pagar.', _mensajes(respuesta))

    def test_con_get_no_borra_nada(self):
        t = self.gasto()
        self.client.get(reverse('eliminar_transaccion', args=[t.pk]))
        self.assertTrue(Transaccion.objects.filter(pk=t.pk).exists())

    def test_no_se_borra_un_movimiento_ajeno(self):
        t = self.gasto(usuario=self.beto)
        respuesta = self.client.post(reverse('eliminar_transaccion', args=[t.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(Transaccion.objects.filter(pk=t.pk).exists())


class PagarGasto(Base):
    def test_marca_el_gasto_pagado_hoy(self):
        t = self.gasto(fecha=self.hoy - timedelta(days=3), pagado=False)
        respuesta = self.client.post(reverse('pagar_gasto', args=[t.pk]))
        t.refresh_from_db()
        self.assertTrue(t.pagado)
        self.assertEqual(t.fecha_pago, self.hoy)
        self.assertIn('Feria: marcado como pagado.', _mensajes(respuesta))

    def test_desde_la_lista_responde_json_con_el_estado(self):
        t = self.gasto(fecha=self.hoy - timedelta(days=3), pagado=False)
        datos = self.client.post(reverse('pagar_gasto', args=[t.pk]), **AJAX).json()
        self.assertEqual(datos['ok'], True)
        self.assertEqual(datos['pagado'], True)
        self.assertTrue(datos['texto'].startswith('Pagado el '))

    def test_un_ingreso_no_se_marca_a_mano(self):
        t = self.gasto(tipo='INGRESO', categoria='Sueldo')
        respuesta = self.client.post(reverse('pagar_gasto', args=[t.pk]))
        self.assertIn('Eso no es un gasto que se marque a mano.', _mensajes(respuesta))
        datos = self.client.post(reverse('pagar_gasto', args=[t.pk]), **AJAX).json()
        self.assertEqual(datos, {'ok': False, 'msg': 'Solo aplica a gastos.'})

    def test_con_get_no_cambia_nada(self):
        t = self.gasto(pagado=False)
        self.client.get(reverse('pagar_gasto', args=[t.pk]))
        t.refresh_from_db()
        self.assertFalse(t.pagado)

    def test_no_se_paga_un_gasto_ajeno(self):
        t = self.gasto(usuario=self.beto, pagado=False)
        self.assertEqual(self.client.post(reverse('pagar_gasto', args=[t.pk])).status_code, 404)

    def test_anular_el_pago_lo_deja_sin_pagar(self):
        t = self.gasto(fecha_pago=self.hoy)
        respuesta = self.client.post(reverse('anular_pago_gasto', args=[t.pk]))
        t.refresh_from_db()
        self.assertFalse(t.pagado)
        self.assertIsNone(t.fecha_pago)
        self.assertIn('Marcado como no pagado.', _mensajes(respuesta))

    def test_anular_desde_la_lista_responde_json(self):
        t = self.gasto(fecha_pago=self.hoy)
        datos = self.client.post(reverse('anular_pago_gasto', args=[t.pk]), **AJAX).json()
        self.assertEqual(datos, {'ok': True, 'pagado': False})

    def test_anular_una_cuota_por_aca_no_la_toca(self):
        t = self.gasto(es_cuota=True, fecha_pago=self.hoy)
        self.client.post(reverse('anular_pago_gasto', args=[t.pk]))
        t.refresh_from_db()
        self.assertTrue(t.pagado)

    def test_anular_con_get_no_cambia_nada(self):
        t = self.gasto(fecha_pago=self.hoy)
        self.client.get(reverse('anular_pago_gasto', args=[t.pk]))
        t.refresh_from_db()
        self.assertTrue(t.pagado)


class GastosPendientes(Base):
    def crear(self, **extra):
        datos = {'nombre': 'Luz', 'monto': '32.500', 'fecha_vencimiento': self.hoy.isoformat()}
        datos.update(extra)
        return self.client.post(reverse('crear_gasto_pendiente'), datos)

    def pendiente(self):
        self.crear()
        return GastoPendiente.objects.get(usuario=self.ana)

    def test_la_pantalla_abre(self):
        self.assertEqual(self.client.get(reverse('crear_gasto_pendiente')).status_code, 200)

    def test_crea_el_gasto_y_su_movimiento_sin_pagar(self):
        respuesta = self.crear()
        gasto = GastoPendiente.objects.get(usuario=self.ana)
        self.assertEqual(gasto.monto, Decimal('32500'))
        self.assertEqual(gasto.categoria, 'Cuentas')
        t = gasto.transaccion
        self.assertEqual(t.descripcion, 'Pendiente: Luz')
        self.assertEqual(t.fecha, self.hoy)
        self.assertFalse(t.pagado)
        self.assertIn('Gasto pendiente agregado y contabilizado.', _mensajes(respuesta))

    def test_respeta_la_categoria_elegida(self):
        self.crear(categoria='Servicios')
        self.assertEqual(GastoPendiente.objects.get(usuario=self.ana).categoria, 'Servicios')

    def test_sin_nombre_monto_o_fecha_no_crea_nada(self):
        for faltante in ('nombre', 'monto', 'fecha_vencimiento'):
            with self.subTest(falta=faltante):
                respuesta = self.crear(**{faltante: ''})
                self.assertIn('Completa nombre, monto y fecha.', _mensajes(respuesta))
        self.assertFalse(GastoPendiente.objects.exists())
        self.assertFalse(Transaccion.objects.exists())

    def test_una_fecha_que_no_existe_no_crea_nada(self):
        respuesta = self.crear(fecha_vencimiento='2026-02-30')
        self.assertIn('La fecha no es válida.', _mensajes(respuesta))
        self.assertFalse(GastoPendiente.objects.exists())

    def test_pagarlo_marca_tambien_el_movimiento(self):
        gasto = self.pendiente()
        self.client.post(reverse('pagar_gasto_pendiente', args=[gasto.pk]))
        gasto.refresh_from_db()
        self.assertTrue(gasto.pagado)
        self.assertEqual(gasto.fecha_pago, date.today())
        self.assertTrue(gasto.transaccion.pagado)

    def test_pagarlo_desde_la_lista_responde_json(self):
        gasto = self.pendiente()
        datos = self.client.post(reverse('pagar_gasto_pendiente', args=[gasto.pk]), **AJAX).json()
        self.assertEqual(datos, {'ok': True})

    def test_anularlo_desmarca_los_dos(self):
        gasto = self.pendiente()
        self.client.post(reverse('pagar_gasto_pendiente', args=[gasto.pk]))
        datos = self.client.post(reverse('anular_gasto_pendiente', args=[gasto.pk]), **AJAX).json()
        self.assertEqual(datos, {'ok': True})
        gasto.refresh_from_db()
        self.assertFalse(gasto.pagado)
        self.assertIsNone(gasto.fecha_pago)
        self.assertFalse(gasto.transaccion.pagado)
        self.assertIsNone(gasto.transaccion.fecha_pago)

    def test_anularlo_sin_lista_avisa(self):
        gasto = self.pendiente()
        self.client.post(reverse('pagar_gasto_pendiente', args=[gasto.pk]))
        respuesta = self.client.post(reverse('anular_gasto_pendiente', args=[gasto.pk]))
        self.assertIn('Marcado como no pagado.', _mensajes(respuesta))

    def test_eliminarlo_borra_el_movimiento(self):
        gasto = self.pendiente()
        respuesta = self.client.post(reverse('eliminar_gasto_pendiente', args=[gasto.pk]))
        self.assertFalse(GastoPendiente.objects.exists())
        self.assertFalse(Transaccion.objects.exists())
        self.assertIn('Gasto pendiente eliminado.', _mensajes(respuesta))

    def test_no_se_toca_un_gasto_pendiente_ajeno(self):
        gasto = self.pendiente()
        self.client.force_login(self.beto)
        for nombre in ('pagar_gasto_pendiente', 'anular_gasto_pendiente', 'eliminar_gasto_pendiente'):
            with self.subTest(vista=nombre):
                self.assertEqual(self.client.post(reverse(nombre, args=[gasto.pk])).status_code, 404)
        gasto.refresh_from_db()
        self.assertFalse(gasto.pagado)
