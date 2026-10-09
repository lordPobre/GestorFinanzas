from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .. import legal
from ..models import UserProfile


class AvisoPoliticaEnInicioTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        perfil.politica_version = '0.1'
        perfil.save()
        self.client.force_login(self.ana)

    def test_el_aviso_cuenta_los_cambios_de_la_version_vigente(self):
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, f'La versión {legal.VERSION} rige desde el {legal.VIGENTE_DESDE}.')
        for titulo, _texto in legal.CAMBIOS:
            self.assertContains(r, titulo)
        self.assertNotContains(r, 'Agrega cuánto se guarda un registro sin confirmar')
