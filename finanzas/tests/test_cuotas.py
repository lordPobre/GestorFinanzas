from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from ..forms import DeudaForm
from ..models import Deuda, PagoCuota, Transaccion
from ..servicios.mes import resumen_mes


class ArrastreCuotasAtrasadasTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user('ana', password='x')
        self.hoy = date.today()
        inicio = (self.hoy.replace(day=10) - timedelta(days=70)).replace(day=10)
        self.deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda',
            monto_total=Decimal('300000'), cuotas_totales=6,
            fecha_inicio=inicio,
        )
        Transaccion.objects.create(
            usuario=self.usuario, tipo='INGRESO', monto=Decimal('1000000'),
            categoria='Sueldo', fecha=self.hoy.replace(day=1),
        )

    def test_el_mes_actual_descuenta_las_cuotas_no_pagadas(self):
        r = resumen_mes(self.usuario, self.hoy.year, self.hoy.month)
        self.assertGreater(r['atrasado_arrastrado'], 0)
        self.assertEqual(
            len(r['cuotas_arrastradas']),
            len([p for p in self.deuda.periodos_atrasados
                 if p < self.hoy.year * 100 + self.hoy.month]),
        )
        esperado = (r['ingresos'] - r['gastos']
                    - r['total_cuotas_mes'] - r['atrasado_arrastrado'])
        self.assertAlmostEqual(r['disponible'], esperado, places=2)

    def test_no_cuenta_dos_veces_la_cuota_del_mes_en_curso(self):
        periodo_actual = self.hoy.year * 100 + self.hoy.month
        r = resumen_mes(self.usuario, self.hoy.year, self.hoy.month)
        self.assertTrue(all(c['periodo'] < periodo_actual
                            for c in r['cuotas_arrastradas']))

    def test_un_mes_pasado_no_arrastra_nada(self):
        anterior = (self.hoy.replace(day=1) - timedelta(days=1))
        r = resumen_mes(self.usuario, anterior.year, anterior.month)
        self.assertEqual(r['atrasado_arrastrado'], 0)
        self.assertEqual(r['cuotas_arrastradas'], [])

    def test_pagar_la_cuota_atrasada_la_saca_del_arrastre(self):
        antes = resumen_mes(self.usuario, self.hoy.year, self.hoy.month)
        p = antes['cuotas_arrastradas'][0]['periodo']
        PagoCuota.objects.create(deuda=self.deuda, periodo=p,
                                 monto=self.deuda.monto_cuota_de(p))
        despues = resumen_mes(self.usuario, self.hoy.year, self.hoy.month)
        self.assertLess(despues['atrasado_arrastrado'],
                        antes['atrasado_arrastrado'])
        self.assertGreater(despues['disponible'], antes['disponible'])


class MontoCuotaDeTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user('ana', password='x')

    def test_reparte_sin_perder_nada_por_redondeo(self):
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda', monto_total=Decimal('1000000'),
            cuotas_totales=12, fecha_inicio=date(2026, 1, 15),
        )
        periodos = deuda.periodos_programados
        total_repartido = sum(
            (deuda.monto_cuota_de(p) for p in periodos), Decimal('0'))
        self.assertEqual(total_repartido, Decimal('1000000'))
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

    def setUp(self):
        self.usuario = User.objects.create_user('ana', password='x')

    def test_periodo_a_pagar_es_el_pendiente_mas_antiguo(self):
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
        inicio = date.today().replace(day=1) - timedelta(days=120)
        inicio = inicio.replace(day=1)
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Compra', monto_total=Decimal('400000'),
            cuotas_totales=10, fecha_inicio=inicio,
        )
        atrasados = deuda.periodos_atrasados
        self.assertTrue(all(deuda.fecha_cobro_de(p) < date.today() for p in atrasados))
        self.assertGreaterEqual(len(atrasados), 3)


class ResumenMesTests(TestCase):

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
        Transaccion.objects.create(
            usuario=self.usuario, tipo='EGRESO', monto=Decimal('50000'),
            categoria='Tecnologia', fecha=date(2026, 6, 10), es_cuota=True)
        Transaccion.objects.create(
            usuario=self.usuario, tipo='EGRESO', monto=Decimal('30000'),
            categoria='Comida', fecha=date(2026, 6, 10), es_cuota=False)

        r = resumen_mes(self.usuario, self.year, self.month)
        self.assertEqual(r['gastos'], 30000.0)


class DeudaFormCuotaTests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user('bruno', password='x')
        self.base = {
            'acreedor': 'Falabella',
            'valor_cuota': '12500',
            'cuotas_totales': '12',
            'fecha_inicio': '2026-09-08',
            'categoria': 'Tecnologia',
        }

    def test_el_total_es_la_cuota_por_la_cantidad(self):
        form = DeudaForm(self.base)
        self.assertTrue(form.is_valid(), form.errors)
        deuda = form.save(commit=False)
        deuda.usuario = self.usuario
        deuda.save()
        self.assertEqual(deuda.monto_total, Decimal('150000'))
        self.assertEqual(deuda.monto_cuota, Decimal('12500'))

    def test_cuota_en_cero_no_pasa(self):
        datos = dict(self.base, valor_cuota='0')
        self.assertFalse(DeudaForm(datos).is_valid())

    def test_al_editar_la_cuota_viene_cargada(self):
        deuda = Deuda.objects.create(
            usuario=self.usuario, acreedor='Tienda',
            monto_total=Decimal('300000'), cuotas_totales=6,
            fecha_inicio=date(2026, 1, 10))
        form = DeudaForm(instance=deuda)
        self.assertEqual(form.fields['valor_cuota'].initial, Decimal('50000'))

    def test_total_desbordado_da_error_en_vez_de_reventar_la_columna(self):
        datos = dict(self.base, valor_cuota='9000000', cuotas_totales='120')
        form = DeudaForm(datos)
        self.assertFalse(form.is_valid())
        self.assertIn('valor_cuota', form.errors)
