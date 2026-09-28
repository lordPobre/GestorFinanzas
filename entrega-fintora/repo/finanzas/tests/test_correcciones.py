from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pyotp
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from .. import google_login
from ..models import (AbonoPrestamo, Categoria, Deuda, PagoCuota, PagoServicio, Persona, Prestamo,
                      SegundoFactor, SesionActiva, Suscripcion, Transaccion, UserProfile)
from ..seguridad import limitar
from ..servicios.panel import desglose_categorias
from ..servicios.suscripciones import generar_cobros_suscripciones
from ..views.cartola import SESION


class EneroDe2027(date):
    @classmethod
    def today(cls):
        return cls(2027, 1, 15)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil = UserProfile.objects.create(usuario=self.ana)


class ReactivarSuscripcion(Base):
    def test_reactivar_en_enero_genera_el_cobro_del_mes(self):
        sub = Suscripcion.objects.create(
            usuario=self.ana, nombre='Spotify', monto=Decimal('5000'), dia_cobro=5,
            activa=False, fecha_inicio=date(2026, 6, 1), fecha_cancelada=date(2026, 10, 1))
        self.client.force_login(self.ana)
        with patch('finanzas.views.suscripciones.date', EneroDe2027), \
                patch('finanzas.servicios.suscripciones.date', EneroDe2027):
            respuesta = self.client.post(reverse('cancelar_suscripcion', args=[sub.pk]))
        self.assertEqual(respuesta.status_code, 302)
        sub.refresh_from_db()
        self.assertTrue(sub.activa)
        self.assertEqual(sub.ultimo_mes_generado, 202701)
        self.assertTrue(Transaccion.objects.filter(usuario=self.ana, fecha=date(2027, 1, 5)).exists())


class CobrosDeMesesSinEntrar(Base):
    def test_los_meses_pasados_quedan_pagados_tambien_en_suscripciones(self):
        hoy = date.today()
        inicio = date(hoy.year, hoy.month, 1) - relativedelta(months=3)
        sub = Suscripcion.objects.create(usuario=self.ana, nombre='Netflix',
                                         monto=Decimal('9000'), dia_cobro=10, fecha_inicio=inicio)
        generar_cobros_suscripciones(self.ana)
        actual = hoy.year * 100 + hoy.month
        pasados = [p for p in sub.periodos_programados if p != actual]
        self.assertEqual(len(pasados), 3)
        self.assertEqual(set(PagoServicio.objects.filter(suscripcion=sub)
                             .values_list('periodo', flat=True)), set(pasados))
        self.assertFalse(any(p in sub.periodos_atrasados for p in pasados))


class CuotaImportadaDesdeCartola(Base):
    def _cargar(self):
        sesion = self.client.session
        sesion[SESION] = {
            'banco': 'x', 'periodo': '', 'cuenta': '', 'cuadra': True, 'descuadre': '0',
            'nota_cuadre': '', 'saldo_inicial': '', 'saldo_final': '',
            'movimientos': [{
                'fecha': '2026-09-10', 'descripcion': 'Tienda', 'monto': '30000',
                'tipo': 'EGRESO', 'categoria': 'Tecnologia', 'cuota_actual': 2,
                'cuota_total': 4, 'es_suscripcion': False, 'ya_existe': False, 'aviso': '',
            }],
        }
        sesion.save()

    def test_la_cuota_del_mes_queda_pagada_y_con_su_movimiento(self):
        self.client.force_login(self.ana)
        self._cargar()
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'deuda_0': '1'})
        deuda = Deuda.objects.get(usuario=self.ana)
        self.assertEqual(deuda.cuotas_totales, 3)
        self.assertEqual(deuda.cuotas_pagadas, 1)
        pago = deuda.pagos.get()
        self.assertEqual(pago.periodo, 202609)
        self.assertEqual(pago.transaccion, Transaccion.objects.get(usuario=self.ana))
        self.assertEqual(deuda.periodo_a_pagar, 202610)

    def test_una_categoria_inventada_no_se_guarda(self):
        self.client.force_login(self.ana)
        self._cargar()
        self.client.post(reverse('confirmar_cartola'), {'sel_0': '1', 'cat_0': 'no-existe'})
        self.assertEqual(Transaccion.objects.get(usuario=self.ana).categoria, 'Tecnologia')


class GoogleSoloVinculaCorreosConfirmados(Base):
    DATOS = {'sub': 'g-1', 'email': 'ana@ejemplo.cl', 'email_verified': True, 'name': 'Ana'}

    def test_no_entra_a_una_cuenta_con_el_correo_sin_confirmar(self):
        usuario, nuevo = google_login._usuario_para(dict(self.DATOS))
        self.assertIsNone(usuario)
        self.perfil.refresh_from_db()
        self.assertIsNone(self.perfil.google_sub)

    def test_no_entra_por_un_correo_escrito_solo_en_el_perfil(self):
        self.ana.email = ''
        self.ana.save(update_fields=['email'])
        self.perfil.email = 'ana@ejemplo.cl'
        self.perfil.save(update_fields=['email'])
        usuario, _ = google_login._usuario_para(dict(self.DATOS))
        self.assertIsNone(usuario)

    def test_vincula_si_el_correo_esta_confirmado(self):
        self.perfil.correo_verificado = True
        self.perfil.save(update_fields=['correo_verificado'])
        usuario, nuevo = google_login._usuario_para(dict(self.DATOS))
        self.assertEqual(usuario, self.ana)
        self.assertFalse(nuevo)

    def test_un_correo_nuevo_crea_la_cuenta(self):
        usuario, nuevo = google_login._usuario_para(dict(self.DATOS, sub='g-2', email='beto@ejemplo.cl'))
        self.assertTrue(nuevo)
        self.assertFalse(usuario.has_usable_password())


class DosPasosEnCuentaSoloGoogle(Base):
    def setUp(self):
        super().setUp()
        self.ana.set_unusable_password()
        self.ana.save()
        self.secreto = pyotp.random_base32()
        SegundoFactor.objects.create(usuario=self.ana, secreto=self.secreto, activo=True)
        self.client.force_login(self.ana)

    def test_se_desactiva_con_un_codigo_valido(self):
        self.client.post(reverse('configurar_2fa'),
                         {'accion': 'desactivar', 'codigo': pyotp.TOTP(self.secreto).now()})
        self.assertFalse(SegundoFactor.objects.filter(usuario=self.ana).exists())

    def test_un_codigo_malo_no_la_desactiva(self):
        self.client.post(reverse('configurar_2fa'), {'accion': 'desactivar', 'codigo': '000000'})
        self.assertTrue(SegundoFactor.objects.filter(usuario=self.ana).exists())


class CategoriasPropiasEnLosGraficos(Base):
    def test_el_inicio_usa_el_nombre_y_el_color_de_la_categoria(self):
        cat = Categoria.objects.create(usuario=self.ana, nombre='Mascotas',
                                       color='#53d258', icono='fa-paw')
        hoy = date.today()
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'),
                                   categoria=cat.slug, fecha=hoy)
        fila = desglose_categorias(self.ana, {'fecha_inicio': date(hoy.year, hoy.month, 1),
                                              'fecha_fin': hoy})[0]
        self.assertEqual(fila['label'], 'Mascotas')
        self.assertEqual(fila['color'], '#53d258')


class BorrarCuentaConBloqueo(Base):
    def test_cinco_fallos_bloquean_aunque_despues_acierte(self):
        self.client.force_login(self.ana)
        for _ in range(5):
            self.client.post(reverse('eliminar_cuenta'), {'confirmacion': 'ELIMINAR', 'password': 'mala'})
        self.client.post(reverse('eliminar_cuenta'),
                         {'confirmacion': 'ELIMINAR', 'password': 'clave-larga-1'})
        self.assertTrue(User.objects.filter(pk=self.ana.pk).exists())


class SesionesSinClaves(Base):
    def test_la_pantalla_no_muestra_la_clave_de_otra_sesion_y_la_cierra_por_numero(self):
        otro = Client()
        otro.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        clave_otra = otro.session.session_key
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})

        cuerpo = self.client.get(reverse('sesiones_activas')).content.decode('utf-8')
        self.assertNotIn(clave_otra, cuerpo)

        fila = SesionActiva.objects.get(clave=clave_otra)
        self.client.post(reverse('sesiones_activas'), {'sesion': fila.pk})
        self.assertFalse(SesionActiva.objects.filter(pk=fila.pk).exists())


class LimiteConVentanaFija(TestCase):
    def setUp(self):
        cache.clear()

    def test_el_vencimiento_no_se_mueve_con_cada_peticion(self):
        def vista_de_prueba(request):
            return HttpResponse('ok')

        vista = limitar(3, 60)(vista_de_prueba)
        pedido = RequestFactory().get('/')
        pedido.user = AnonymousUser()
        clave = 'limite:vista_de_prueba:127.0.0.1'

        vista(pedido)
        primero = cache.get(clave)
        vista(pedido)
        segundo = cache.get(clave)
        self.assertEqual(segundo[0], 2)
        self.assertEqual(primero[1], segundo[1])


class CategoriaConValoresDeLaLista(Base):
    def test_valores_fuera_de_la_lista_se_reemplazan(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('crear_categoria'), {
            'nombre': 'Rara', 'tipo': 'OTRO', 'color': 'red;background:url(x)', 'icono': 'fa-x" a="'})
        cat = Categoria.objects.get(usuario=self.ana)
        self.assertEqual((cat.tipo, cat.color, cat.icono), ('EGRESO', '#ffaa2c', 'fa-tag'))


class CobrosVinculadosALaSuscripcion(Base):
    def test_editar_la_suscripcion_no_pierde_el_vinculo_con_el_pago(self):
        hoy = date.today()
        sub = Suscripcion.objects.create(usuario=self.ana, nombre='Spotify', monto=Decimal('5000'),
                                         dia_cobro=28, fecha_inicio=date(hoy.year, hoy.month, 1))
        generar_cobros_suscripciones(self.ana)
        self.client.force_login(self.ana)
        self.client.post(reverse('editar_suscripcion', args=[sub.pk]), {
            'nombre': 'Spotify Familiar', 'monto': '8000', 'dia_cobro': '28',
            'categoria': 'Suscripciones'})
        cobro = sub.cobros.get()
        self.assertEqual(cobro.descripcion, 'Suscripción: Spotify Familiar')
        self.assertEqual(cobro.monto, Decimal('8000'))

        self.client.post(reverse('pagar_servicio', args=[sub.pk]))
        cobro.refresh_from_db()
        self.assertTrue(cobro.pagado)


class PrestamosConDecimal(Base):
    def test_la_cuota_y_el_saldo_son_exactos(self):
        persona = Persona.objects.create(usuario=self.ana, nombre='Beto')
        prestamo = Prestamo.objects.create(persona=persona, descripcion='Viaje', monto=Decimal('100000'),
                                           tipo='CUOTAS', cuotas_totales=3)
        self.assertEqual(prestamo.monto_cuota, Decimal('33333'))
        AbonoPrestamo.objects.create(prestamo=prestamo, monto=Decimal('33333'))
        prestamo = Prestamo.objects.get(pk=prestamo.pk)
        self.assertEqual(prestamo.cuotas_abonadas, 1)
        self.assertEqual(prestamo.monto_pendiente, Decimal('66667'))
        self.assertIsInstance(persona.total_pendiente, Decimal)


class ContadorDeCuotasPagadas(Base):
    def test_se_mantiene_solo_al_pagar_y_al_anular(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('300000'),
                                     cuotas_totales=3, fecha_inicio=date(2026, 1, 10))
        pago = PagoCuota.objects.create(deuda=deuda, periodo=202601, monto=Decimal('100000'))
        deuda.refresh_from_db()
        self.assertEqual(deuda.cuotas_pagadas, 1)
        pago.delete()
        deuda.refresh_from_db()
        self.assertEqual(deuda.cuotas_pagadas, 0)
