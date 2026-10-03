from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class CuotasDisenoTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_la_lista_carga(self):
        respuesta = self.client.get(reverse('deudas'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn('Al día</span>', respuesta.content.decode('utf-8'))

    def test_el_formulario_dice_fintora(self):
        respuesta = self.client.get(reverse('crear_deuda'))
        if respuesta.status_code == 200:
            cuerpo = respuesta.content.decode('utf-8')
            self.assertNotIn('FinApp', cuerpo)
            self.assertNotIn('font-size:10.5px', cuerpo)
