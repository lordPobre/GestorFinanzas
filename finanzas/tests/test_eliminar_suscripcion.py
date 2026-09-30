from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ..models import Suscripcion, Transaccion, UserProfile
from ..servicios.suscripciones import generar_cobros_suscripciones


class EliminarSuscripcionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.create(usuario=self.ana)
        self.client.force_login(self.ana)

    def _sub(self, nombre, inicio):
        sub = Suscripcion.objects.create(usuario=self.ana, nombre=nombre, monto=Decimal('5990'),
                                         dia_cobro=1, fecha_inicio=inicio)
        generar_cobros_suscripciones(self.ana)
        return sub

    def _cobros(self, nombre):
        return Transaccion.objects.filter(usuario=self.ana, tipo='EGRESO', descripcion=f'Suscripción: {nombre}')

    def test_borra_los_gastos_si_se_pide(self):
        sub = self._sub('Prueba', date.today())
        self.assertEqual(self._cobros('Prueba').count(), 1)
        self.client.post(reverse('eliminar_suscripcion', args=[sub.pk]), {'borrar_gastos': '1'})
        self.assertFalse(Suscripcion.objects.filter(pk=sub.pk).exists())
        self.assertEqual(self._cobros('Prueba').count(), 0)

    def test_conserva_los_gastos_si_no_se_pide(self):
        sub = self._sub('Netflix', date.today() - relativedelta(months=3))
        antes = self._cobros('Netflix').count()
        self.client.post(reverse('eliminar_suscripcion', args=[sub.pk]))
        self.assertFalse(Suscripcion.objects.filter(pk=sub.pk).exists())
        self.assertEqual(self._cobros('Netflix').count(), antes)

    def test_no_toca_gastos_de_otra_suscripcion(self):
        prueba = self._sub('Prueba', date.today())
        self._sub('Spotify', date.today())
        self.client.post(reverse('eliminar_suscripcion', args=[prueba.pk]), {'borrar_gastos': '1'})
        self.assertEqual(self._cobros('Spotify').count(), 1)

    def test_casilla_sugerida_segun_el_caso(self):
        nueva = self._sub('Prueba', date.today())
        vieja = self._sub('Netflix', date.today() - relativedelta(months=3))
        subs = {s.pk: s for s in self.client.get(reverse('suscripciones')).context['suscripciones']}
        self.assertTrue(subs[nueva.pk].borrar_cobros_sugerido)
        self.assertFalse(subs[vieja.pk].borrar_cobros_sugerido)
        self.assertEqual(subs[vieja.pk].cobros_cantidad, 4)
