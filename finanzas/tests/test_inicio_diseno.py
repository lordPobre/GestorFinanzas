from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class InicioDisenoTests(TestCase):
    def test_la_leyenda_muestra_lo_que_queda(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('Te queda $', cuerpo)
