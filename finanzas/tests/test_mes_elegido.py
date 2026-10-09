from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from ..models import Transaccion
from ..servicios.mes_elegido import mes_pedido, selector_mes

HOY = date(2026, 10, 9)


class MesPedidoTests(TestCase):

    def pedir(self, mes):
        return mes_pedido(RequestFactory().get('/', {'mes': mes}), HOY)

    def test_lee_el_mes_de_la_url(self):
        self.assertEqual(self.pedir('2026-08'), (2026, 8))

    def test_un_mes_invalido_o_futuro_vuelve_al_actual(self):
        for valor in ('', 'agosto', '2026-13', '2026-11', '1999-05'):
            self.assertEqual(self.pedir(valor), (2026, 10), valor)


class SelectorMesTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def gasto(self, fecha, monto, categoria='Comida'):
        return Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                          categoria=categoria, fecha=fecha)

    def test_ofrece_desde_el_primer_movimiento_hasta_hoy(self):
        self.gasto(date(2026, 7, 3), '1000')
        sel = selector_mes(self.ana, 2026, 8, HOY)
        self.assertEqual([o['valor'] for o in sel['opciones']],
                         ['2026-10', '2026-09', '2026-08', '2026-07'])
        self.assertTrue(sel['opciones'][2]['elegido'])
        self.assertEqual(sel['anterior']['valor'], '2026-07')
        self.assertEqual(sel['siguiente']['valor'], '2026-09')
        self.assertEqual(sel['ref_anterior'], 'en julio')
        self.assertEqual(sel['en_mes'], 'en agosto')

    def test_en_el_mes_actual_no_deja_avanzar(self):
        sel = selector_mes(self.ana, 2026, 10, HOY)
        self.assertIsNone(sel['siguiente'])
        self.assertTrue(sel['es_actual'])
        self.assertEqual(sel['en_mes'], 'este mes')


class PantallasConMesTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        hoy = date.today()
        self.este = hoy.replace(day=1)
        self.antes = date(hoy.year - 1, 12, 1) if hoy.month == 1 else date(hoy.year, hoy.month - 1, 1)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('15000'),
                                   categoria='Transporte', fecha=self.antes)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('9000'),
                                   categoria='Comida', fecha=self.este)

    def valor(self, f):
        return f'{f.year}-{f.month:02d}'

    def test_estadisticas_muestra_las_categorias_del_mes_elegido(self):
        r = self.client.get(reverse('estadisticas'), {'mes': self.valor(self.antes)})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([c['nombre'] for c in r.context['ranking']], ['Transporte'])
        r = self.client.get(reverse('estadisticas'))
        self.assertEqual([c['nombre'] for c in r.context['ranking']], ['Comida'])

    def test_categorias_suma_lo_gastado_en_el_mes_elegido(self):
        r = self.client.get(reverse('categorias'), {'mes': self.valor(self.antes)})
        self.assertEqual(r.status_code, 200)
        gastado = {c['slug']: c['gastado'] for c in r.context['de_gasto']}
        self.assertEqual(gastado.get('Transporte'), 15000)
        self.assertEqual(gastado.get('Comida'), 0)
        self.assertContains(r, 'data-mes-elegir')
