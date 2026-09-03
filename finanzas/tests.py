"""Tests sobre lo que no puede fallar en silencio: las fórmulas de dinero.

No es una suite completa — es la que evita que alguien cambie una fórmula
de saldo o de cuotas y el bug llegue a producción sin que nada avise.
Cubre: el redondeo de cuotas (Deuda.monto_cuota_de), qué mes toca pagar y
cuáles están atrasados (periodo_a_pagar / periodos_atrasados), y el
resumen del mes (resumen_mes) con montos conocidos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Deuda, PagoCuota, Transaccion
from .views import resumen_mes


class MontoCuotaDeTests(TestCase):
    """La última cuota debe absorber el residuo del redondeo, siempre."""

    def setUp(self):
        self.usuario = User.objects.create_user('ana', password='x')

    def test_reparte_sin_perder_nada_por_redondeo(self):
        # $1.000.000 en 12 cuotas: 83.333,33... por cuota. Sin el ajuste de
        # la última, 12 * 83.333 = 999.996 — se pierden $4 por el camino.
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda', monto_total=Decimal('1000000'),
            cuotas_totales=12, fecha_inicio=date(2026, 1, 15),
        )
        periodos = deuda.periodos_programados
        total_repartido = sum(
            (deuda.monto_cuota_de(p) for p in periodos), Decimal('0'))
        self.assertEqual(total_repartido, Decimal('1000000'))
        # Las primeras 11 son la cuota redondeada; la última absorbe el resto.
        for p in periodos[:-1]:
            self.assertEqual(deuda.monto_cuota_de(p), Decimal('83333'))
        self.assertEqual(deuda.monto_cuota_de(periodos[-1]), Decimal('83337'))

    def test_division_exacta_no_deja_residuo_en_la_ultima(self):
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda', monto_total=Decimal('1200000'),
            cuotas_totales=12, fecha_inicio=date(2026, 1, 15),
        )
        periodos = deuda.periodos_programados
        self.assertEqual(deuda.monto_cuota_de(periodos[-1]), Decimal('100000'))


class PeriodosDeudaTests(TestCase):
    """Qué mes toca pagar y cuáles están atrasados: la base de los badges
    de urgencia en toda la app."""

    def setUp(self):
        self.usuario = User.objects.create_user('ana', password='x')

    def test_periodo_a_pagar_es_el_pendiente_mas_antiguo(self):
        # Empezó hace 3 meses, nadie ha pagado nada: el más viejo primero.
        inicio = date.today().replace(day=1) - timedelta(days=90)
        inicio = inicio.replace(day=1)
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Compra', monto_total=Decimal('300000'),
            cuotas_totales=6, fecha_inicio=inicio,
        )
        self.assertEqual(deuda.periodo_a_pagar, deuda.periodos_programados[0])

    def test_pagar_el_mas_antiguo_avanza_al_siguiente(self):
        inicio = date.today().replace(day=1) - timedelta(days=60)
        inicio = inicio.replace(day=1)
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Compra', monto_total=Decimal('300000'),
            cuotas_totales=6, fecha_inicio=inicio,
        )
        primero = deuda.periodos_programados[0]
        PagoCuota.objects.create(deuda=deuda, periodo=primero,
                                  monto=deuda.monto_cuota_de(primero))
        self.assertEqual(deuda.periodo_a_pagar, deuda.periodos_programados[1])

    def test_pagar_un_mes_futuro_no_lo_marca_como_atrasado_ni_pendiente(self):
        # Adelantarse a un pago no debe dejar huecos raros: ese periodo
        # simplemente sale de pendientes y atrasados.
        inicio = date.today().replace(day=1)
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Compra', monto_total=Decimal('120000'),
            cuotas_totales=3, fecha_inicio=inicio,
        )
        futuro = deuda.periodos_programados[-1]
        PagoCuota.objects.create(deuda=deuda, periodo=futuro,
                                  monto=deuda.monto_cuota_de(futuro))
        self.assertNotIn(futuro, deuda.periodos_pendientes)
        self.assertNotIn(futuro, deuda.periodos_atrasados)

    def test_periodos_atrasados_solo_cuenta_los_que_ya_vencieron(self):
        # Empezó hace 4 meses y no se ha pagado nada: los meses ya pasados
        # deben salir como atrasados; el mes en curso o futuros, no.
        inicio = date.today().replace(day=1) - timedelta(days=120)
        inicio = inicio.replace(day=1)
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Compra', monto_total=Decimal('400000'),
            cuotas_totales=10, fecha_inicio=inicio,
        )
        # periodos_atrasados compara la FECHA de cobro contra hoy, no el
        # periodo en sí: el mes en curso puede salir atrasado si su día de
        # cobro (el mismo día que fecha_inicio) ya pasó este mes.
        atrasados = deuda.periodos_atrasados
        self.assertTrue(all(deuda.fecha_cobro_de(p) < date.today() for p in atrasados))
        self.assertGreaterEqual(len(atrasados), 3)


class ResumenMesTests(TestCase):
    """resumen_mes es la fuente de 'ingresos', 'gastos' y 'disponible' que
    se muestra en el dashboard, el panel de registro y el sidebar. Si esto
    se rompe, se rompe toda la app a la vez."""

    def setUp(self):
        self.usuario = User.objects.create_user('ana', password='x')
        self.year, self.month = 2026, 6

    def test_ingresos_y_gastos_del_mes(self):
        Transaccion.objects.create(
            usuario=self.usuario, tipo='INGRESO', monto=Decimal('1000000'),
            categoria='Sueldo', fecha=date(2026, 6, 5))
        Transaccion.objects.create(
            usuario=self.usuario, tipo='EGRESO', monto=Decimal('200000'),
            categoria='Comida', fecha=date(2026, 6, 10))
        # Un ingreso o gasto de otro mes no debe contarse.
        Transaccion.objects.create(
            usuario=self.usuario, tipo='EGRESO', monto=Decimal('999999'),
            categoria='Comida', fecha=date(2026, 5, 10))

        r = resumen_mes(self.usuario, self.year, self.month)
        self.assertEqual(r['ingresos'], 1000000.0)
        self.assertEqual(r['gastos'], 200000.0)
        self.assertEqual(r['disponible'], 800000.0)

    def test_cuota_del_mes_se_suma_completa_una_sola_vez(self):
        Transaccion.objects.create(
            usuario=self.usuario, tipo='INGRESO', monto=Decimal('1000000'),
            categoria='Sueldo', fecha=date(2026, 6, 5))
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda', monto_total=Decimal('600000'),
            cuotas_totales=6, fecha_inicio=date(2026, 6, 1))

        r = resumen_mes(self.usuario, self.year, self.month)
        self.assertEqual(r['total_cuotas_mes'], 100000.0)
        self.assertEqual(r['cuotas_pendientes_mes'], 100000.0)
        self.assertEqual(r['cuotas_pagadas_mes'], 0.0)
        # comprometido = gastos del día a día (0) + cuotas del mes (100000)
        self.assertEqual(r['comprometido'], 100000.0)
        self.assertEqual(r['disponible'], 900000.0)

    def test_cuota_pagada_se_cuenta_como_pagada_no_como_pendiente(self):
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda', monto_total=Decimal('300000'),
            cuotas_totales=3, fecha_inicio=date(2026, 6, 1))
        periodo = self.year * 100 + self.month
        PagoCuota.objects.create(deuda=deuda, periodo=periodo,
                                  monto=deuda.monto_cuota_de(periodo))

        r = resumen_mes(self.usuario, self.year, self.month)
        self.assertEqual(r['cuotas_pagadas_mes'], 100000.0)
        self.assertEqual(r['cuotas_pendientes_mes'], 0.0)
        self.assertEqual(r['total_cuotas_mes'], 100000.0)

    def test_gasto_marcado_como_cuota_no_se_duplica_en_gastos_del_dia_a_dia(self):
        # es_cuota=True: resumen_mes debe excluirlo de 'gastos' porque las
        # cuotas se suman aparte (ver comentario en resumen_mes).
        Transaccion.objects.create(
            usuario=self.usuario, tipo='EGRESO', monto=Decimal('50000'),
            categoria='Tecnologia', fecha=date(2026, 6, 10), es_cuota=True)
        Transaccion.objects.create(
            usuario=self.usuario, tipo='EGRESO', monto=Decimal('30000'),
            categoria='Comida', fecha=date(2026, 6, 10), es_cuota=False)

        r = resumen_mes(self.usuario, self.year, self.month)
        self.assertEqual(r['gastos'], 30000.0)
