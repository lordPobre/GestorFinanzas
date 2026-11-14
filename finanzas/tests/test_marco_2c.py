from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class Marco2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _html(self, nombre):
        return self.client.get(reverse(nombre), follow=True).content.decode('utf-8')

    def test_el_encabezado_dice_la_seccion_y_no_trae_saludo_ni_botones(self):
        html = self._html('deudas')
        self.assertIn('<span class="topbar-titulo-2c">Pagos</span>', html)
        self.assertNotIn('topbar-saludo', html)
        self.assertNotIn('Anotar ingreso</span>', html)

    def test_ninguna_pantalla_carga_las_pieles_viejas(self):
        for nombre in ('metas', 'encuesta', 'sesiones_activas', 'actividad_cuenta', 'crear_deuda'):
            with self.subTest(pantalla=nombre):
                html = self._html(nombre)
                self.assertNotIn('tema-2c', html)
                self.assertIn('css/fintora-2c.css', html)
