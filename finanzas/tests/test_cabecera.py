from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CabeceraConPerfilTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1', is_staff=True)
        self.client.force_login(self.ana)

    def test_las_pantallas_sueltas_traen_el_perfil_para_la_cabecera(self):
        for nombre in ['encuesta', 'encuesta_resultados', 'eliminar_cuenta']:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.context['profile'].usuario, self.ana)
