from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno, fechas
from finanzas.models import Deuda


class Cuotas2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _cuotas(self, con_2c=True):
        if con_2c:
            self.client.cookies[diseno.COOKIE] = diseno.VALOR
        return self.client.get(reverse('deudas'))

    def test_sin_la_cookie_sigue_la_pantalla_actual(self):
        respuesta = self._cuotas(con_2c=False)
        self.assertTemplateUsed(respuesta, 'finanzas/deudas.html')
        self.assertTemplateNotUsed(respuesta, 'finanzas/deudas_2c.html')

    def test_con_la_cookie_usa_cuotas_2c(self):
        respuesta = self._cuotas()
        self.assertTemplateUsed(respuesta, 'finanzas/deudas_2c.html')
        self.assertContains(respuesta, 'aria-current="page">Cuotas</a>')
        self.assertContains(respuesta, 'Nueva compra en cuotas')
        self.assertContains(respuesta, 'name="valor_cuota"')
        self.assertContains(respuesta, 'Mes a mes')

    def test_cada_compra_trae_lo_que_necesita_editar(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('120000'),
                                     cuotas_totales=12, fecha_inicio=fechas.hoy())
        respuesta = self._cuotas()
        self.assertContains(respuesta, f'data-accion="{reverse("editar_deuda", args=[deuda.pk])}"')
        self.assertContains(respuesta, f'data-eliminar="{reverse("eliminar_deuda", args=[deuda.pk])}"')
        self.assertContains(respuesta, 'data-cuota="10000"')
        self.assertContains(respuesta, 'data-cuotas="12"')
        self.assertContains(respuesta, 'Pagar cuota de')

    def test_editar_desde_el_panel_guarda_con_el_formulario_de_siempre(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('120000'),
                                     cuotas_totales=12, fecha_inicio=fechas.hoy())
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        self.client.post(reverse('editar_deuda', args=[deuda.pk]), {
            'acreedor': 'Notebook Lenovo', 'valor_cuota': '15000', 'cuotas_totales': '6',
            'fecha_inicio': fechas.hoy().isoformat(), 'categoria': deuda.categoria,
            'next': reverse('deudas'),
        })
        deuda.refresh_from_db()
        self.assertEqual(deuda.acreedor, 'Notebook Lenovo')
        self.assertEqual(deuda.monto_total, Decimal('90000'))
