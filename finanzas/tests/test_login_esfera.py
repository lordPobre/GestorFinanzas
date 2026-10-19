from django.test import TestCase
from django.urls import reverse


class LoginEsferaTests(TestCase):

    def test_el_login_trae_la_esfera_y_el_boton_entrar(self):
        cuerpo = self.client.get(reverse('login')).content.decode('utf-8')
        self.assertIn('<div class="auth lm">', cuerpo)
        self.assertIn('class="lpo amarillo"', cuerpo)
        self.assertIn('class="marca-svg"', cuerpo)
        self.assertIn('data-lm-abrir', cuerpo)
        self.assertEqual(cuerpo.count('data-lm-cerrar'), 3)
        self.assertIn('css/landing-esfera.css', cuerpo)
        self.assertIn('css/login-esfera.css', cuerpo)
        self.assertIn('js/pantallas/login-esfera.js', cuerpo)

    def test_con_un_error_la_hoja_parte_abierta(self):
        cuerpo = self.client.post(reverse('login'), {'username': 'nadie', 'password': 'mala-clave-1'}).content.decode('utf-8')
        self.assertIn('<div class="auth lm abierto">', cuerpo)
        self.assertIn('Usuario o contraseña incorrectos', cuerpo)

    def test_las_otras_pantallas_de_acceso_no_cambian(self):
        cuerpo = self.client.get(reverse('registro')).content.decode('utf-8')
        self.assertIn('<div class="auth">', cuerpo)
        self.assertNotIn('lm-hero', cuerpo)
        self.assertNotIn('login-esfera', cuerpo)
