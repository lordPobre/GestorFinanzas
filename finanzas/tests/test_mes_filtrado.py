from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .. import fechas
from ..models import Deuda, PagoCuota, PagoServicio, Persona, Prestamo, Suscripcion
from ..servicios.mes import deudas_del_mes, resumen_mes, suscripciones_del_mes
from ..views.comun import contadores


def _periodo(f):
    return f.year * 100 + f.month


class DeudasDelMesTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = fechas.hoy()
        self.este = self.hoy.replace(day=1)

    def _deuda(self, nombre, inicio, cuotas, pagadas=()):
        d = Deuda.objects.create(usuario=self.ana, acreedor=nombre, monto_total=Decimal(10000 * cuotas),
                                 cuotas_totales=cuotas, fecha_inicio=inicio)
        for p in pagadas:
            PagoCuota.objects.create(deuda=d, periodo=p, monto=Decimal('10000'), fecha_pago=inicio)
        return d

    def _nombres(self, con_atrasos):
        return set(deudas_del_mes(self.ana, self.hoy.year, self.hoy.month, con_atrasos)
                   .values_list('acreedor', flat=True))

    def test_solo_trae_las_que_tienen_cuota_o_algo_atrasado(self):
        hace_un_anio = self.este - relativedelta(years=1)
        self._deuda('Vieja pagada', hace_un_anio, 3,
                    [_periodo(hace_un_anio + relativedelta(months=i)) for i in range(3)])
        self._deuda('Vieja con atraso', hace_un_anio, 3, [_periodo(hace_un_anio)])
        self._deuda('De este mes', self.este, 6)
        self._deuda('Futura', self.este + relativedelta(months=2), 3)
        self._deuda('Empezó antes y sigue', self.este - relativedelta(months=2), 6)
        self.assertEqual(self._nombres(False), {'De este mes', 'Empezó antes y sigue'})
        self.assertEqual(self._nombres(True), {'De este mes', 'Empezó antes y sigue', 'Vieja con atraso'})

    def test_un_pago_fuera_del_plazo_no_esconde_un_atraso(self):
        inicio = self.este - relativedelta(months=4)
        fuera = _periodo(inicio - relativedelta(months=1))
        self._deuda('Fecha editada', inicio, 2, [_periodo(inicio), fuera])
        self.assertIn('Fecha editada', self._nombres(True))
        r = resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        self.assertEqual(r['comprometido'], Decimal('10000'))

    def test_las_cuotas_del_mes_dan_lo_mismo_que_antes(self):
        self._deuda('A', self.este - relativedelta(months=1), 3, [_periodo(self.este - relativedelta(months=1))])
        self._deuda('B', self.este, 2)
        r = resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        self.assertEqual(r['total_cuotas_mes'], 20000.0)
        self.assertEqual(len([e for dia in r['eventos'].values() for e in dia]), 2)


class SuscripcionesDelMesTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = fechas.hoy()

    def test_respeta_el_inicio_la_cancelacion_y_el_futuro(self):
        este = self.hoy.replace(day=1)
        Suscripcion.objects.create(usuario=self.ana, nombre='Activa', monto=Decimal('5990'),
                                   fecha_inicio=este - relativedelta(months=3))
        Suscripcion.objects.create(usuario=self.ana, nombre='Cancelada antes', monto=Decimal('5990'),
                                   fecha_inicio=este - relativedelta(months=6), activa=False,
                                   fecha_cancelada=este - relativedelta(months=2))
        Suscripcion.objects.create(usuario=self.ana, nombre='Nueva el mes que viene', monto=Decimal('5990'),
                                   fecha_inicio=este + relativedelta(months=1))
        nombres = set(suscripciones_del_mes(self.ana, self.hoy.year, self.hoy.month, self.hoy)
                      .values_list('nombre', flat=True))
        self.assertEqual(nombres, {'Activa'})
        siguiente = este + relativedelta(months=1)
        self.assertFalse(suscripciones_del_mes(self.ana, siguiente.year, siguiente.month, self.hoy).exists())


class ContadoresGuardadosTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.sub = Suscripcion.objects.create(usuario=self.ana, nombre='Música', monto=Decimal('5990'),
                                              fecha_inicio=date(2026, 1, 1))

    def _consultas(self):
        with CaptureQueriesContext(connection) as c:
            datos = contadores(self.ana)
        return datos, len(c.captured_queries)

    def test_la_segunda_vez_cuesta_menos(self):
        _, primera = self._consultas()
        _, segunda = self._consultas()
        self.assertLess(segunda, primera)

    def test_se_actualiza_al_pagar_una_suscripcion(self):
        self.assertEqual(contadores(self.ana)['subs_pendientes'], 1)
        hoy = fechas.hoy()
        PagoServicio.objects.create(suscripcion=self.sub, periodo=_periodo(hoy), monto=Decimal('5990'),
                                    fecha_pago=hoy)
        self.assertEqual(contadores(self.ana)['subs_pendientes'], 0)

    def test_se_actualiza_con_un_prestamo_nuevo(self):
        self.assertEqual(contadores(self.ana)['prestamos_activos'], 0)
        camila = Persona.objects.create(usuario=self.ana, nombre='Camila', lado='ME_DEBE')
        Prestamo.objects.create(persona=camila, descripcion='Arriendo', monto=Decimal('180000'),
                                tipo='UNICO', cuotas_totales=1)
        self.assertEqual(contadores(self.ana)['prestamos_activos'], 1)

    def test_se_actualiza_con_una_compra_en_cuotas(self):
        self.assertEqual(contadores(self.ana)['cuotas_activas'], 0)
        Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('60000'),
                             cuotas_totales=6, fecha_inicio=fechas.hoy())
        self.assertEqual(contadores(self.ana)['cuotas_activas'], 1)
