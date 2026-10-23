from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ..models import Deuda, GastoPendiente, MetaAhorro, PagoCuota


class CalendarioInicioTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.hoy = date.today()
        self.deuda = Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('90000'),
                                          cuotas_totales=3, fecha_inicio=self.hoy.replace(day=10))
        self.otra = Deuda.objects.create(usuario=self.ana, acreedor='Celular', monto_total=Decimal('60000'),
                                         cuotas_totales=6, fecha_inicio=self.hoy.replace(day=20))
        PagoCuota.objects.create(deuda=self.otra, periodo=Deuda.periodo_de(self.hoy.year, self.hoy.month),
                                 monto=Decimal('10000'), fecha_pago=self.hoy)
        self.meta = MetaAhorro.objects.create(usuario=self.ana, nombre='Viaje', monto_meta=Decimal('500000'))

    def _inicio(self):
        return self.client.get(reverse('dashboard')).content.decode()

    def _calendario(self, **params):
        return self.client.get(reverse('inicio_calendario'), params)

    def test_inicio_deja_el_calendario_para_cuando_se_abre(self):
        html = self._inicio()
        self.assertIn('id="modalCalendario"', html)
        self.assertIn(f'data-fragmento="{reverse("inicio_calendario")}?year={self.hoy.year}&amp;month={self.hoy.month}"', html)
        self.assertNotIn('class="cal-day', html)
        self.assertNotIn('id="dia10"', html)
        self.assertNotIn('Ya pagados', html)

    def test_inicio_ya_no_lleva_los_modales_de_aporte(self):
        html = self._inicio()
        self.assertNotIn(f'id="meta{self.meta.pk}"', html)
        self.assertNotIn(reverse('aportar_meta', args=[self.meta.pk]), html)
        self.assertIn(f'{reverse("metas")}#meta{self.meta.pk}', html)

    def test_el_calendario_trae_los_dias_y_los_pagados(self):
        respuesta = self._calendario(year=self.hoy.year, month=self.hoy.month)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'no-store')
        html = respuesta.content.decode()
        self.assertIn('data-calendario-caja', html)
        self.assertIn('class="cal-day', html)
        self.assertIn('data-open="#dia10"', html)
        self.assertIn('id="dia10"', html)
        self.assertIn('id="dia20"', html)
        self.assertIn(reverse('pagar_cuota', args=[self.deuda.pk]), html)
        self.assertIn('Ya pagados', html)
        self.assertIn('Celular', html)
        self.assertNotIn('<html', html)

    def test_lleva_las_cuentas_de_otros_meses(self):
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('23000'),
                                      fecha_vencimiento=self.hoy.replace(day=1))
        html = self._calendario().content.decode()
        self.assertIn('Cuentas de otros meses', html)
        self.assertIn('Luz', html)

    def test_un_mes_invalido_muestra_el_actual(self):
        html = self._calendario(year='x', month='13').content.decode()
        self.assertIn('id="dia10"', html)

    def test_no_muestra_lo_de_otra_persona(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        Deuda.objects.create(usuario=beto, acreedor='Ajeno', monto_total=Decimal('30000'),
                             cuotas_totales=3, fecha_inicio=self.hoy.replace(day=5))
        self.assertNotIn('Ajeno', self._calendario().content.decode())

    def test_sin_sesion_pide_entrar(self):
        self.client.logout()
        respuesta = self._calendario()
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])
