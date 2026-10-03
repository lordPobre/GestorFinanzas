from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AnalisisDisenoTests(TestCase):
    def test_la_pantalla_carga(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        respuesta = self.client.get(reverse('analisis_predictivo'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('chip-vidrio al-dia">Te sobra', respuesta.content.decode('utf-8'))
