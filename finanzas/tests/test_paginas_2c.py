from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from finanzas import diseno, plantillas_2c

PLANTILLAS = Path(settings.BASE_DIR) / 'finanzas' / 'templates'
ESTATICOS = Path(settings.BASE_DIR) / 'static'


class ErroresTests(TestCase):
    def test_la_404_va_en_papel_con_la_esfera_gris(self):
        respuesta = self.client.get('/esta-pagina-no-existe/')
        self.assertEqual(respuesta.status_code, 404)
        cuerpo = respuesta.content.decode('utf-8')
        self.assertIn('class="er gris"', cuerpo)
        self.assertIn('class="er-esfera"', cuerpo)
        self.assertIn('content="#F3EFE7"', cuerpo)

    def test_las_paginas_de_error_tienen_su_tono(self):
        for nombre, tono in (('500.html', 'coral'), ('403.html', 'coral'), ('403_csrf.html', 'ambar'), ('400.html', 'ambar')):
            with self.subTest(nombre=nombre):
                self.assertIn('{% block tono %}' + tono, (PLANTILLAS / nombre).read_text('utf-8'))

    def test_la_hoja_de_errores_es_clara(self):
        hoja = (ESTATICOS / 'css' / 'errores.css').read_text('utf-8')
        self.assertIn('#F3EFE7', hoja)
        self.assertIn('Familjen Grotesk', hoja)


class BienvenidaTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_con_el_2c_la_bienvenida_va_en_papel(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        respuesta = self.client.get(reverse('onboarding'))
        self.assertContains(respuesta, 'css/bienvenida-2c.css')
        self.assertContains(respuesta, 'id="cajaCuotaOb"')
        self.assertContains(respuesta, 'data-atajos="#ingreso_monto"')

    def test_sin_el_2c_sigue_la_de_siempre(self):
        self.assertNotContains(self.client.get(reverse('onboarding')), 'css/bienvenida-2c.css')

    def test_la_plantilla_2c_esta_en_el_mapa(self):
        self.assertEqual(plantillas_2c.PLANTILLAS['finanzas/onboarding.html'], 'finanzas/onboarding_2c.html')


class CookiesYCompartirTests(SimpleTestCase):
    def test_el_aviso_de_cookies_tiene_su_version_2c(self):
        self.assertIn('html.f2c .cookies', (ESTATICOS / 'css' / 'consentimiento.css').read_text('utf-8'))

    def test_las_imagenes_nuevas_son_png(self):
        for nombre in ('og-fintora.png', 'correo-cabecera.png'):
            with self.subTest(nombre=nombre):
                self.assertTrue((ESTATICOS / 'img' / nombre).read_bytes().startswith(b'\x89PNG'))
