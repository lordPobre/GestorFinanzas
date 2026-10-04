from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas.models import MetaAhorro


class MetasOrbitaTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.meta = MetaAhorro.objects.create(usuario=self.ana, nombre='Festivales', monto_meta=1000000, monto_actual=40000)

    def test_la_tarjeta_trae_anillo_y_aporte_rapido(self):
        cuerpo = self.client.get(reverse('metas')).content.decode('utf-8')
        self.assertIn('class="me-orbita"', cuerpo)
        self.assertIn('data-meta-rapido', cuerpo)
        self.assertIn('class="me-menu"', cuerpo)
        self.assertIn('data-faltante="960000"', cuerpo)

    def test_el_aporte_rapido_suma(self):
        self.client.post(reverse('aportar_meta', args=[self.meta.pk]), {'monto': '30000', 'next': reverse('metas')})
        self.meta.refresh_from_db()
        self.assertEqual(int(self.meta.monto_actual), 70000)
