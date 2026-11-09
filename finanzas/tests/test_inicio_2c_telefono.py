from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno


class Inicio2cTelefonoTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.client.cookies[diseno.COOKIE] = diseno.VALOR

    def test_trae_lo_que_viene_como_el_prototipo(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        self.assertIn('<h2>Lo que viene</h2>', cuerpo)
        self.assertIn('Pagaste todo lo de', cuerpo)
        self.assertIn('i2c-tarjeta i2c-solo-esc', cuerpo)
