from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno


class Secciones2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_prestamos_va_dentro_de_las_pestanas_de_pagos(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        respuesta = self.client.get(reverse('prestamos'))
        self.assertContains(respuesta, 'aria-current="page">Préstamos</a>')
        self.assertContains(respuesta, 'css/pagos-2c.css')

    def test_prestamos_sin_la_cookie_no_cambia(self):
        respuesta = self.client.get(reverse('prestamos'))
        self.assertNotContains(respuesta, 'p2c-pestanas')
        self.assertNotContains(respuesta, 'css/pagos-2c.css')

    def test_plan_y_tu_cargan_el_tema_2c(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        for nombre in ('metas', 'plan_plata', 'estadisticas', 'analisis_predictivo',
                       'perfil', 'categorias', 'importar_cartola', 'clave_api'):
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre), follow=True)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, '<html lang="es" class="t2c">')
                self.assertContains(respuesta, 'css/tema-2c.css')
