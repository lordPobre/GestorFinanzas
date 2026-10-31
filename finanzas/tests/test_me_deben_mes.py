from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from finanzas.models import AbonoPrestamo, Persona, Prestamo
from finanzas.servicios.me_deben_mes import ATRAS, Plan, indice, por_mes
from finanzas.templatetags.moneda import money

HOY = date(2026, 10, 20)


class Base(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def prestamo(self, nombre, descripcion, monto, fecha, cuotas=0, lado='ME_DEBE', usuario=None):
        persona, _ = Persona.objects.get_or_create(usuario=usuario or self.ana, nombre=nombre, lado=lado)
        return Prestamo.objects.create(persona=persona, descripcion=descripcion, monto=Decimal(monto),
                                       tipo='CUOTAS' if cuotas else 'UNICO', cuotas_totales=cuotas or 1,
                                       fecha=fecha)

    def abonar(self, prestamo, monto, fecha):
        AbonoPrestamo.objects.create(prestamo=prestamo, monto=Decimal(monto), fecha=fecha)

    def datos(self):
        personas = Persona.objects.filter(usuario=self.ana, lado='ME_DEBE').prefetch_related('prestamos__abonos')
        return por_mes(personas, HOY)


class PorMesTests(Base):

    def setUp(self):
        super().setUp()
        self.notebook = self.prestamo('Claude', 'Notebook', '300000', date(2026, 8, 5), cuotas=3)
        self.abonar(self.notebook, '100000', date(2026, 8, 10))
        self.super = self.prestamo('Mamá', 'Supermercado', '60000', date(2026, 7, 1), cuotas=6)
        for mes in (7, 8, 9, 10):
            self.abonar(self.super, '10000', date(2026, mes, 2))
        self.unico = self.prestamo('Camila', 'Préstamo', '20000', date(2026, 6, 15))
        self.abonar(self.unico, '10000', date(2026, 8, 1))

    def mes(self, escenario, desfase):
        return self.datos()['escenarios'][escenario]['meses'][ATRAS + desfase]

    def test_la_primera_cuota_vence_en_el_mes_del_prestamo(self):
        plan = Plan(self.notebook, self.notebook.persona)
        self.assertEqual(plan.vence_en(indice(date(2026, 7, 1))), 0)
        self.assertEqual(plan.vence_en(indice(date(2026, 8, 1))), Decimal('100000'))
        self.assertEqual(plan.vence_en(indice(date(2026, 11, 1))), 0)

    def test_los_meses_cerrados_usan_los_abonos(self):
        agosto, septiembre = self.mes('aldia', -2), self.mes('aldia', -1)
        self.assertEqual(agosto['real'], 120000)
        self.assertEqual(agosto['esperado'], 110000)
        self.assertEqual(septiembre['saldo'], 240000)
        self.assertEqual(septiembre['tipo'], 'real')

    def test_la_cuota_que_no_llego_aparece_en_su_mes(self):
        septiembre = self.mes('aldia', -1)
        faltas = [e for e in septiembre['eventos'] if e['tipo'] == 'falta']
        self.assertEqual(len(faltas), 1)
        self.assertEqual(faltas[0]['nombre'], 'Claude')
        self.assertIn('cuota 2 de 3', faltas[0]['detalle'])
        self.assertEqual(faltas[0]['monto'], money(100000))

    def test_al_dia_lo_atrasado_se_cobra_este_mes(self):
        datos = self.datos()['escenarios']['aldia']
        self.assertEqual(datos['meses'][ATRAS]['proy'], 200000)
        self.assertEqual(datos['meses'][ATRAS + 1]['proy'], 10000)
        self.assertEqual(datos['meses'][ATRAS + 1]['saldo'], 20000)
        self.assertEqual(datos['resumen']['cero_valor'], 'Dic 2026')
        self.assertIn(money(100000), datos['resumen']['mes_sub'])

    def test_segun_como_pagan_usa_las_cuotas_pagadas_a_tiempo(self):
        datos = self.datos()['escenarios']['ritmo']
        self.assertEqual(datos['meses'][ATRAS]['proy'], 100000)
        self.assertEqual(datos['meses'][ATRAS + 1]['proy'], 60000)
        claude = next(p for p in datos['personas'] if p['nombre'] == 'Claude')
        self.assertEqual(claude['ritmo_txt'], 'Pagó 1 de 2 cuotas a tiempo')

    def test_el_pago_unico_queda_fuera_de_la_proyeccion(self):
        datos = self.datos()
        self.assertIn('Camila', datos['sin_fecha_txt'])
        self.assertIn(money(10000), datos['escenarios']['aldia']['resumen']['cero_sub'])
        camila = next(p for p in datos['escenarios']['aldia']['personas'] if p['nombre'] == 'Camila')
        self.assertEqual(camila['estado'], 'sinfecha')
        self.assertEqual(camila['fin_txt'], 'Sin fecha de pago')

    def test_las_personas_van_de_mayor_a_menor_deuda(self):
        personas = self.datos()['escenarios']['aldia']['personas']
        self.assertEqual([p['nombre'] for p in personas], ['Claude', 'Mamá', 'Camila'])
        self.assertEqual(personas[0]['estado'], 'atrasado')
        self.assertEqual(personas[0]['estado_txt'], f'Atrasado {money(100000)}')
        self.assertEqual(personas[1]['estado'], 'aldia')
        self.assertEqual(personas[1]['fin_txt'], 'Termina en dic 2026')

    def test_un_prestamo_saldado_no_aparece_en_personas(self):
        self.abonar(self.unico, '10000', date(2026, 10, 5))
        nombres = [p['nombre'] for p in self.datos()['escenarios']['aldia']['personas']]
        self.assertNotIn('Camila', nombres)
        self.assertEqual(self.datos()['sin_fecha_txt'], '')


class SinPrestamosTests(Base):

    def test_sin_prestamos_no_hay_datos(self):
        Persona.objects.create(usuario=self.ana, nombre='Sola', lado='ME_DEBE')
        self.assertIsNone(self.datos())


class PantallaTests(Base):

    def setUp(self):
        super().setUp()
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.prestamo('Claude', 'Notebook', '300000', date.today(), cuotas=3)
        self.client.force_login(self.ana)

    def test_me_deben_trae_la_seccion_mes_a_mes(self):
        respuesta = self.client.get(reverse('prestamos'))
        self.assertContains(respuesta, 'id="datosPorMes"')
        self.assertContains(respuesta, 'js/pantallas/me-deben-mes.js')
        self.assertContains(respuesta, 'css/me-deben-mes.css')

    def test_debo_no_la_trae(self):
        self.prestamo('Banco', 'Préstamo', '100000', date.today(), lado='LE_DEBO')
        respuesta = self.client.get(reverse('prestamos') + '?lado=debo')
        self.assertNotContains(respuesta, 'id="datosPorMes"')

    def test_no_mezcla_prestamos_de_otra_cuenta(self):
        self.prestamo('Zoe', 'Ajeno', '50000', date.today(), cuotas=2, usuario=self.beto)
        respuesta = self.client.get(reverse('prestamos'))
        self.assertNotContains(respuesta, 'Zoe')
