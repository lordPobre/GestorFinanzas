from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


PLANTILLAS = {
    'prestamos': 'finanzas/prestamos_2c.html',
    'metas': 'finanzas/metas_2c.html',
    'plan_plata': 'finanzas/plan_2c.html',
    'estadisticas': 'finanzas/estadisticas_2c.html',
    'analisis_predictivo': 'finanzas/analisis_2c.html',
    'perfil': 'finanzas/perfil_2c.html',
    'categorias': 'finanzas/categorias_2c.html',
    'importar_cartola': 'finanzas/importar_cartola_2c.html',
    'clave_api': 'finanzas/clave_api_2c.html',
}


class Secciones2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_prestamos_va_dentro_de_las_pestanas_de_pagos(self):
        respuesta = self.client.get(reverse('prestamos'))
        self.assertContains(respuesta, 'aria-current="page">Préstamos</a>')
        self.assertContains(respuesta, 'css/pagos-2c.css')
        self.assertContains(respuesta, 'id="modalPersona"')
        self.assertContains(respuesta, 'id="segTipoPersona"')

    def test_plan_y_tu_tienen_su_plantilla_2c(self):
        for nombre, plantilla in PLANTILLAS.items():
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre), follow=True)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTemplateUsed(respuesta, plantilla)
                self.assertTemplateUsed(respuesta, 'finanzas/base_2c.html')
                self.assertContains(respuesta, '<html lang="es" class="t2c f2c">')
                self.assertContains(respuesta, 'css/secciones-2c.css')
                self.assertNotContains(respuesta, 'css/finapp.css')
