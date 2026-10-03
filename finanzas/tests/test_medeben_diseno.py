from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class MeDebenDisenoTests(TestCase):
    def test_la_lista_carga_sin_estilos_sueltos_en_el_resumen(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        respuesta = self.client.get(reverse('prestamos'))
        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('class="md-resumen"', cuerpo)
        self.assertNotIn('Al día</span>', cuerpo)
