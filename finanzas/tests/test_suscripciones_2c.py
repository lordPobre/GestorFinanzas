from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas.models import Suscripcion


class Suscripciones2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _subs(self):
        return self.client.get(reverse('suscripciones'))

    def test_usa_suscripciones_2c(self):
        respuesta = self._subs()
        self.assertTemplateUsed(respuesta, 'finanzas/suscripciones_2c.html')
        self.assertContains(respuesta, 'aria-current="page">Suscripciones</a>')
        self.assertContains(respuesta, 'css/suscripciones-2c.css')
        self.assertContains(respuesta, 'Nueva suscripción')
        self.assertContains(respuesta, 'No tienes suscripciones registradas')

    def test_cada_suscripcion_trae_pagar_y_eliminar(self):
        s = Suscripcion.objects.create(usuario=self.ana, nombre='Netflix', monto=Decimal('9990'),
                                       dia_cobro=28, fecha_inicio=date(2026, 1, 1))
        respuesta = self._subs()
        self.assertContains(respuesta, 'Netflix')
        self.assertContains(respuesta, f'id="eliminarSub{s.pk}"')
        self.assertContains(respuesta, reverse('editar_suscripcion', args=[s.pk]))
        self.assertContains(respuesta, 'Pagas al mes')
