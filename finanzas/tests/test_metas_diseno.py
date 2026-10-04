from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas.models import MetaAhorro


class MetasDisenoTests(TestCase):
    def test_aportar_esta_a_la_vista(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        MetaAhorro.objects.create(usuario=ana, nombre='Viaje', monto_meta=500000, monto_actual=100000)
        cuerpo = self.client.get(reverse('metas')).content.decode('utf-8')
        self.assertIn('class="me-aportar"', cuerpo)
        self.assertIn('class="me-linea"', cuerpo)
        self.assertNotIn('Meta cumplida', cuerpo)
