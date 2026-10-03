from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas.models import Persona


class MeDebenEscritorioTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.camila = Persona.objects.create(usuario=self.ana, nombre='Camila', contacto='')
        self.claude = Persona.objects.create(usuario=self.ana, nombre='Claude', contacto='')

    def test_el_detalle_y_la_lista_de_personas(self):
        cuerpo = self.client.get(reverse('detalle_persona', args=[self.camila.pk])).content.decode('utf-8')
        self.assertIn('md-lista md-dos', cuerpo)
        self.assertIn('class="md-card md-detalle"', cuerpo)
        self.assertIn('aria-current="page"', cuerpo)
        self.assertEqual(cuerpo.count('class="md-fila'), 2)

    def test_sin_personas_se_ve_el_vacio(self):
        Persona.objects.all().delete()
        cuerpo = self.client.get(reverse('prestamos')).content.decode('utf-8')
        self.assertIn('Nadie te debe', cuerpo)
        self.assertNotIn('md-dos', cuerpo)
