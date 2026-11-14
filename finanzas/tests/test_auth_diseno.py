from django.test import TestCase, override_settings
from django.urls import reverse


class RegistroDisenoTests(TestCase):
    def test_usa_los_componentes_del_ingreso(self):
        cuerpo = self.client.get(reverse('registro')).content.decode('utf-8')
        self.assertIn('auth-btn ambar', cuerpo)
        self.assertIn('class="auth-cab"', cuerpo)
        self.assertEqual(cuerpo.count('data-ver-pass='), 2)
        self.assertIn('(opcional)', cuerpo)
        self.assertNotIn('autofocus', cuerpo)

    @override_settings(GOOGLE_CLIENT_ID='prueba')
    def test_ofrece_google_si_esta_activo(self):
        cuerpo = self.client.get(reverse('registro')).content.decode('utf-8')
        self.assertIn('id="btnGoogle"', cuerpo)
        self.assertEqual(cuerpo.count('data-acepta-google'), 1)

    @override_settings(GOOGLE_CLIENT_ID='')
    def test_sin_google_no_hay_boton(self):
        cuerpo = self.client.get(reverse('registro')).content.decode('utf-8')
        self.assertNotIn('id="btnGoogle"', cuerpo)
