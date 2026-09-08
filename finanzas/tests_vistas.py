"""Tests de vistas: quién puede ver qué.

Los tests de finanzas/tests.py cubren las fórmulas de dinero. Estos cubren
la otra cosa que no puede fallar en silencio: que los datos de una persona
no se le muestren a otra.

El riesgo concreto es sencillo de describir. Casi todas las URL llevan el id
del objeto (`/pagar-cuota/42/`), y basta con que una vista nueva se olvide
del filtro `usuario=request.user` para que cualquiera pueda leer o borrar
datos ajenos cambiando un número en la barra de direcciones. No es un ataque
sofisticado: es escribir otro número.

La lista PROTEGIDAS de abajo es la parte importante de este archivo. Al
agregar una vista que reciba el id de algo, agregar también su entrada acá.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (Deuda, GastoPendiente, MetaAhorro, PagoCuota, Persona,
                     Prestamo, Suscripcion, Transaccion)


class BaseDosUsuarios(TestCase):
    """Dos cuentas con un juego completo de datos cada una."""

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.de_ana = self._crear_datos(self.ana)
        self.de_beto = self._crear_datos(self.beto)

    def _crear_datos(self, usuario):
        deuda = Deuda.objects.create(
            usuario=usuario, acreedor='Tienda', monto_total=Decimal('600000'),
            cuotas_totales=6, fecha_inicio=date(2026, 1, 10))
        transaccion = Transaccion.objects.create(
            usuario=usuario, tipo='EGRESO', monto=Decimal('15000'),
            categoria='Comida', fecha=date(2026, 6, 3), pagado=False)
        persona = Persona.objects.create(usuario=usuario, nombre='Deudor')
        prestamo = Prestamo.objects.create(
            persona=persona, descripcion='Préstamo', monto=Decimal('50000'))
        meta = MetaAhorro.objects.create(
            usuario=usuario, nombre='Viaje', monto_meta=Decimal('300000'))
        sub = Suscripcion.objects.create(
            usuario=usuario, nombre='Streaming', monto=Decimal('9900'),
            fecha_inicio=date(2026, 1, 1))
        gasto = GastoPendiente.objects.create(
            usuario=usuario, nombre='Luz', monto=Decimal('30000'),
            fecha_vencimiento=date(2026, 6, 20))
        return {
            'deuda': deuda, 'transaccion': transaccion, 'persona': persona,
            'prestamo': prestamo, 'meta': meta, 'sub': sub, 'gasto': gasto,
        }


class AislamientoEntreUsuariosTests(BaseDosUsuarios):
    """Beto no puede tocar nada de Ana."""

    # (nombre de la url, clave del objeto, método)
    PROTEGIDAS = [
        ('editar_deuda', 'deuda', 'post'),
        ('pagar_cuota', 'deuda', 'post'),
        ('anular_cuota', 'deuda', 'post'),
        ('eliminar_deuda', 'deuda', 'post'),
        ('editar_transaccion', 'transaccion', 'post'),
        ('eliminar_transaccion', 'transaccion', 'post'),
        ('pagar_gasto', 'transaccion', 'post'),
        ('anular_pago_gasto', 'transaccion', 'post'),
        ('detalle_persona', 'persona', 'get'),
        ('eliminar_persona', 'persona', 'post'),
        ('crear_prestamo', 'persona', 'post'),
        ('abonar_prestamo', 'prestamo', 'post'),
        ('eliminar_prestamo', 'prestamo', 'post'),
        ('aportar_meta', 'meta', 'post'),
        ('editar_meta', 'meta', 'post'),
        ('eliminar_meta', 'meta', 'post'),
        ('pagar_servicio', 'sub', 'post'),
        ('anular_pago_servicio', 'sub', 'post'),
        ('cancelar_suscripcion', 'sub', 'post'),
        ('eliminar_suscripcion', 'sub', 'post'),
        ('pagar_gasto_pendiente', 'gasto', 'post'),
        ('anular_gasto_pendiente', 'gasto', 'post'),
        ('eliminar_gasto_pendiente', 'gasto', 'post'),
    ]

    def test_no_puede_alcanzar_objetos_de_otro_usuario(self):
        self.client.force_login(self.beto)
        for nombre, clave, metodo in self.PROTEGIDAS:
            objeto = self.de_ana[clave]
            with self.subTest(url=nombre):
                url = reverse(nombre, args=[objeto.pk])
                respuesta = getattr(self.client, metodo)(url, {'monto': '1000'})
                self.assertEqual(
                    respuesta.status_code, 404,
                    f'{nombre} respondió {respuesta.status_code} con un objeto '
                    f'de otro usuario; debía ser 404.',
                )

    def test_los_datos_de_ana_siguen_intactos(self):
        """Que responda 404 no basta: hay que comprobar que no alcanzó a
        escribir nada antes de rechazar."""
        self.client.force_login(self.beto)
        for nombre, clave, metodo in self.PROTEGIDAS:
            url = reverse(nombre, args=[self.de_ana[clave].pk])
            getattr(self.client, metodo)(url, {'monto': '1000'})

        self.assertTrue(Deuda.objects.filter(pk=self.de_ana['deuda'].pk).exists())
        self.assertTrue(Persona.objects.filter(pk=self.de_ana['persona'].pk).exists())
        self.assertTrue(MetaAhorro.objects.filter(pk=self.de_ana['meta'].pk).exists())
        self.assertTrue(Suscripcion.objects.filter(pk=self.de_ana['sub'].pk).exists())
        self.assertEqual(PagoCuota.objects.filter(deuda=self.de_ana['deuda']).count(), 0)
        self.assertEqual(
            MetaAhorro.objects.get(pk=self.de_ana['meta'].pk).monto_actual,
            Decimal('0'))

    def test_las_listas_solo_muestran_lo_propio(self):
        self.client.force_login(self.beto)
        for nombre in ['dashboard', 'deudas', 'prestamos', 'metas',
                       'suscripciones', 'estadisticas']:
            with self.subTest(url=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)

        respuesta = self.client.get(reverse('prestamos'))
        personas = respuesta.context['personas']
        self.assertTrue(all(p.usuario_id == self.beto.pk for p in personas))
        self.assertNotIn(self.de_ana['persona'], personas)


class SesionRequeridaTests(BaseDosUsuarios):
    """Sin sesión, todo redirige al acceso. Ninguna pantalla se escapa."""

    PUBLICAS = {'login', 'registro', 'recuperar', 'restablecer',
                'logout', 'service_worker'}

    def test_las_pantallas_privadas_piden_entrar(self):
        for nombre in ['dashboard', 'deudas', 'prestamos', 'metas', 'categorias',
                       'suscripciones', 'estadisticas', 'perfil',
                       'analisis_predictivo', 'exportar_excel', 'exportar_csv']:
            with self.subTest(url=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn('/login/', respuesta['Location'])

    def test_una_vista_de_detalle_no_filtra_por_redireccion(self):
        """Sin sesión debe redirigir, no responder 404: un 404 confirmaría
        que el id existe."""
        url = reverse('detalle_persona', args=[self.de_ana['persona'].pk])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 302)


class ConsultasPorPantallaTests(BaseDosUsuarios):
    """Candados sobre las consultas N+1 ya corregidas.

    No miden rendimiento: comprueban que las propiedades siguen leyendo del
    prefetch en vez de consultar de nuevo. Si alguien vuelve a poner un
    .count() o un values_list() en el camino, estos tests lo detienen.
    """

    def test_periodos_pagados_de_deuda_no_consulta_si_hay_prefetch(self):
        deuda = self.de_ana['deuda']
        periodo = deuda.periodos_programados[0]
        PagoCuota.objects.create(deuda=deuda, periodo=periodo,
                                 monto=deuda.monto_cuota_de(periodo))

        deudas = list(Deuda.objects.filter(usuario=self.ana).prefetch_related('pagos'))
        with self.assertNumQueries(0):
            for d in deudas:
                d.periodos_pagados
                d.periodos_pendientes
                d.periodo_a_pagar
                d.periodos_atrasados

    def test_periodos_pagados_de_suscripcion_no_consulta_si_hay_prefetch(self):
        subs = list(Suscripcion.objects.filter(usuario=self.ana).prefetch_related('pagos'))
        with self.assertNumQueries(0):
            for s in subs:
                s.periodos_pagados
                s.pagada_este_mes
                s.estado_mes

    def test_cantidad_prestamos_no_consulta_si_hay_prefetch(self):
        personas = list(Persona.objects.filter(usuario=self.ana)
                        .prefetch_related('prestamos__abonos'))
        with self.assertNumQueries(0):
            for p in personas:
                p.cantidad_prestamos
                p.resumen_meta
                p.total_pendiente
