from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class Anotar2cTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_la_hoja_de_anotar_trae_su_estilo_y_su_script(self):
        cuerpo = self.client.get(reverse('dashboard')).content.decode('utf-8')
        for pieza in ('css/anotar-2c.css', 'css/revisar-2c.css', 'css/dialogos-2c.css', 'js/pantallas/anotar-2c.js',
                      'placeholder="Nota"', 'id="segFecha"', 'id="segPago"', 'id="btnGuardar"'):
            self.assertIn(pieza, cuerpo)
