from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class EntrarComoElPrototipoTests(TestCase):

    def test_abre_con_la_huella_y_la_contrasena_aparte(self):
        cuerpo = self.client.get(reverse('login')).content.decode('utf-8')
        for pieza in ('data-modo="rapido"', 'id="bloquePasskey" class="ac2c-rapido" hidden', 'Usar mi contraseña',
                      'data-modo-ir="clave"', 'data-modo-ir="rapido"', 'class="ac2c-esfera"',
                      'Tus datos quedan en tu cuenta. Nada se comparte.', 'js/pantallas/login-2c.js'):
            self.assertIn(pieza, cuerpo)
        self.assertNotIn('o con tu contraseña', cuerpo)
        self.assertNotIn('ac2c-legal', cuerpo)

    def test_con_un_error_abre_con_la_contrasena(self):
        User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        respuesta = self.client.post(reverse('login'), {'username': 'ana', 'password': 'otra-clave'})
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('data-modo="clave"', cuerpo)
        self.assertIn('Usuario o contraseña incorrectos', cuerpo)
