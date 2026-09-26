from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LandingTests(TestCase):
    def test_sin_sesion_se_ve_la_landing(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'finanzas/landing.html')
        self.assertContains(respuesta, reverse('registro'))
        self.assertContains(respuesta, reverse('login'))

    def test_con_sesion_se_ve_el_inicio(self):
        ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(ana)
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, 'finanzas/dashboard.html')

    def test_la_app_instalada_sin_sesion_va_al_acceso(self):
        respuesta = self.client.get(reverse('dashboard') + '?fuente=pwa')
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)

    def test_la_landing_no_trae_scripts_sin_nonce(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        for trozo in cuerpo.split('<script')[1:]:
            self.assertIn('nonce=', trozo.split('>')[0])
