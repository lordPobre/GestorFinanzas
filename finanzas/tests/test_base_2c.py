from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


PANTALLAS_2C = ('dashboard', 'por_pagar', 'deudas', 'suscripciones')


class Base2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_las_pantallas_2c_usan_la_base_nueva_sin_las_hojas_viejas(self):
        for nombre in PANTALLAS_2C:
            with self.subTest(pantalla=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertTemplateUsed(respuesta, 'finanzas/base_2c.html')
                cuerpo = respuesta.content.decode('utf-8')
                self.assertIn('<html lang="es" class="t2c f2c">', cuerpo)
                self.assertIn('css/fintora-2c.css', cuerpo)
                for vieja in ('finapp.css', 'tema-vidrio.css', 'tema-2c.css', 'tema-2c-auto.css', 'sesion.css'):
                    self.assertNotIn('css/' + vieja, cuerpo)

    def test_la_base_nueva_trae_lo_que_usan_los_scripts(self):
        cuerpo = self.client.get(reverse('deudas')).content.decode('utf-8')
        for pieza in ('id="modalGasto"', 'id="modalAvisos"', 'class="sidebar-nav"', 'class="bottomnav barra-2c"',
                      'class="f2c-salud"', 'class="topbar-titulo-2c"', 'js/finapp.js', 'js/pantallas/panel-carga.js',
                      'data-tour="salud"'):
            self.assertIn(pieza, cuerpo)
