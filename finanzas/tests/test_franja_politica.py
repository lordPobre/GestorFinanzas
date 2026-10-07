from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import legal
from finanzas.models import UserProfile

TITULO = 'Cambió la política de privacidad'


class FranjaDeLaPoliticaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        self.perfil.politica_version = '1.5'
        self.perfil.save(update_fields=['politica_version'])
        self.client.force_login(self.ana)

    def _aceptar(self, **extra):
        return self.client.post(reverse('perfil'), {'accion': 'aceptar_politica', **extra})

    def test_sale_a_quien_no_acepto_la_version_vigente(self):
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, TITULO)
        self.assertContains(r, legal.VERSION)
        self.assertContains(r, reverse('privacidad'))

    def test_no_sale_a_quien_ya_la_acepto(self):
        self.perfil.politica_version = legal.VERSION
        self.perfil.save(update_fields=['politica_version'])
        self.assertNotContains(self.client.get(reverse('dashboard')), TITULO)

    def test_aceptar_desde_la_franja_vuelve_al_inicio_y_la_quita(self):
        r = self._aceptar(next=reverse('dashboard'))
        self.assertRedirects(r, reverse('dashboard'), fetch_redirect_response=False)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.politica_version, legal.VERSION)
        self.assertIsNotNone(self.perfil.politica_aceptada)
        self.assertNotContains(self.client.get(reverse('dashboard')), TITULO)

    def test_sin_next_sigue_volviendo_al_perfil(self):
        self.assertRedirects(self._aceptar(), reverse('perfil'), fetch_redirect_response=False)

    def test_next_no_lleva_fuera_del_sitio(self):
        r = self._aceptar(next='https://ejemplo.cl/')
        self.assertEqual(r.status_code, 302)
        self.assertFalse(r['Location'].startswith('https://ejemplo.cl'))
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.politica_version, legal.VERSION)
