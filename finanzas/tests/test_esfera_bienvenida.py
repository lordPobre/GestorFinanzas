from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import UserProfile
from ..servicios.esfera_bienvenida import bienvenida_esfera


class TextosTests(SimpleTestCase):

    def test_sigue_igual(self):
        self.assertEqual(bienvenida_esfera('verde', 'verde')['texto'], 'Tus finanzas siguen sanas.')

    def test_empeora(self):
        datos = bienvenida_esfera('rojo', 'verde')
        self.assertEqual(datos['cambio'], 'peor')
        self.assertIn('cambiaron de estado', datos['texto'])

    def test_mejora(self):
        self.assertEqual(bienvenida_esfera('verde', 'amarillo')['cambio'], 'mejor')

    def test_primera_vez(self):
        self.assertEqual(bienvenida_esfera('amarillo', '')['texto'], 'Estás cerca del límite.')


class AlEntrarTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.update_or_create(usuario=self.ana, defaults={
            'onboarding_completado': True, 'nombre_completo': 'Ana Pérez'})

    def _entrar(self):
        self.client.post(reverse('login'), {'username': 'ana', 'password': 'clave-larga-1'})

    def test_solo_la_primera_visita_trae_el_saludo(self):
        self._entrar()
        primera = self.client.get(reverse('dashboard'))
        self.assertContains(primera, 'data-bienvenida=')
        self.assertContains(primera, 'data-esfera-hola')
        segunda = self.client.get(reverse('dashboard'))
        self.assertNotContains(segunda, 'data-bienvenida=')
