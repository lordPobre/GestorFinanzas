from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class EstadisticasDisenoTests(TestCase):
    def test_la_pantalla_carga_con_las_metricas_nuevas(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        respuesta = self.client.get(reverse('estadisticas'))
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('es-hoja', cuerpo)
        self.assertEqual(cuerpo.count('class="es-metrica-etq"'), 4)
