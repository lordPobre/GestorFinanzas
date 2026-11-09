from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno, fechas
from finanzas.models import Deuda


class Inicio2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _inicio(self, con_2c=True):
        if con_2c:
            self.client.cookies[diseno.COOKIE] = diseno.VALOR
        return self.client.get(reverse('dashboard'))

    def test_sin_la_cookie_sigue_el_inicio_actual(self):
        respuesta = self._inicio(con_2c=False)
        self.assertTemplateUsed(respuesta, 'finanzas/dashboard.html')
        self.assertTemplateNotUsed(respuesta, 'finanzas/dashboard_2c.html')
        self.assertContains(respuesta, 'name="apple-mobile-web-app-status-bar-style" content="black-translucent"')

    def test_con_la_cookie_usa_el_inicio_2c(self):
        respuesta = self._inicio()
        self.assertTemplateUsed(respuesta, 'finanzas/dashboard_2c.html')
        self.assertContains(respuesta, 'css/inicio-2c.css')
        self.assertContains(respuesta, 'js/pantallas/inicio-2c.js')
        self.assertContains(respuesta, 'Cómo sale la cifra')
        self.assertContains(respuesta, 'Cuotas del mes')
        self.assertContains(respuesta, 'name="apple-mobile-web-app-status-bar-style" content="default"')

    def test_las_cuotas_de_meses_anteriores_van_aparte(self):
        hoy = fechas.hoy()
        inicio = date(hoy.year, hoy.month, 1) - relativedelta(months=2)
        Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('30000'),
                             cuotas_totales=3, fecha_inicio=inicio)
        respuesta = self._inicio()
        self.assertContains(respuesta, 'Cuotas que no pagaste')
        self.assertContains(respuesta, 'de cuotas que no pagaste')
        self.assertContains(respuesta, 'En cuotas este mes')

    def test_sin_cuotas_no_aparece_lo_atrasado(self):
        respuesta = self._inicio()
        self.assertNotContains(respuesta, 'Cuotas que no pagaste')
        self.assertContains(respuesta, 'No te quedan cuotas')
