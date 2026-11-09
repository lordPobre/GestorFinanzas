from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno, fechas
from finanzas.models import Deuda


class PagosMes2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _pagos(self, con_2c=True):
        if con_2c:
            self.client.cookies[diseno.COOKIE] = diseno.VALOR
        return self.client.get(reverse('por_pagar'))

    def _deuda_atrasada(self):
        hoy = fechas.hoy()
        inicio = date(hoy.year, hoy.month, 1) - relativedelta(months=2)
        return Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('30000'),
                                    cuotas_totales=3, fecha_inicio=inicio)

    def test_sin_la_cookie_sigue_la_pantalla_actual(self):
        respuesta = self._pagos(con_2c=False)
        self.assertTemplateUsed(respuesta, 'finanzas/por_pagar.html')
        self.assertTemplateNotUsed(respuesta, 'finanzas/por_pagar_2c.html')

    def test_con_la_cookie_usa_pagos_2c_con_pestanas(self):
        respuesta = self._pagos()
        self.assertTemplateUsed(respuesta, 'finanzas/por_pagar_2c.html')
        self.assertContains(respuesta, 'css/pagos-2c.css')
        self.assertContains(respuesta, 'aria-current="page">Este mes</a>')
        for nombre in ('deudas', 'suscripciones', 'prestamos'):
            self.assertContains(respuesta, f'href="{reverse(nombre)}" class="p2c-pestana"')

    def test_las_cuotas_de_meses_anteriores_se_pueden_pagar_desde_aqui(self):
        deuda = self._deuda_atrasada()
        respuesta = self._pagos()
        self.assertContains(respuesta, 'De meses anteriores')
        self.assertContains(respuesta, 'no la pagaste', count=2)
        self.assertContains(respuesta, 'Cuotas de meses anteriores')
        self.assertContains(respuesta, reverse('pagar_cuota', args=[deuda.pk]))
        primero = deuda.periodos_programados[0]
        self.client.post(reverse('pagar_cuota', args=[deuda.pk]),
                         {'periodo': primero, 'next': reverse('por_pagar')})
        self.assertEqual(deuda.pagos.filter(periodo=primero).count(), 1)
        self.assertContains(self._pagos(), 'no la pagaste', count=1)

    def test_otro_mes_no_muestra_lo_arrastrado(self):
        self._deuda_atrasada()
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        hoy = fechas.hoy()
        antes = date(hoy.year, hoy.month, 1) - relativedelta(months=1)
        respuesta = self.client.get(reverse('por_pagar'), {'mes': f'{antes.year}-{antes.month:02d}'})
        self.assertNotContains(respuesta, 'De meses anteriores')
