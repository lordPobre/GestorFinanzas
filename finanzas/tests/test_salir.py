from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SalirTests(TestCase):

    def test_salir_limpia_la_memoria_del_navegador(self):
        self.client.force_login(User.objects.create_user('eva', password='x'))
        r = self.client.post(reverse('logout'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Clear-Site-Data'], '"cache"')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_despues_de_salir_el_inicio_no_muestra_datos(self):
        self.client.force_login(User.objects.create_user('leo', password='x'))
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('perfil')).status_code, 302)
        r = self.client.get(reverse('dashboard'))
        self.assertNotContains(r, 'formRegistro')
