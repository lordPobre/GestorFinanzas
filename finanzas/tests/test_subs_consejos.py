from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from finanzas.models import Suscripcion


class ConsejosSuscripcionesTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        for nombre, monto in (('Netflix', 9900), ('Spotify', 4500), ('Amazon Prime', 6500)):
            Suscripcion.objects.create(usuario=self.ana, nombre=nombre, monto=monto, categoria='Suscripciones', dia_cobro=5)

    def test_el_ahorro_es_lo_que_se_paga_de_mas(self):
        respuesta = self.client.get(reverse('suscripciones'))
        grupo = respuesta.context['duplicadas'][0]
        self.assertEqual(grupo['ahorro_anual'], (9900 + 6500) * 12)
        self.assertEqual(respuesta.context['ahorro_total'], (9900 + 6500) * 12)
        self.assertEqual([i.nombre for i in grupo['items']], ['Spotify', 'Amazon Prime', 'Netflix'])

    def test_el_consejo_va_fuera_de_la_lista(self):
        cuerpo = self.client.get(reverse('suscripciones')).content.decode('utf-8')
        self.assertIn('data-consejos', cuerpo)
        self.assertIn('No son lo mismo', cuerpo)
        self.assertNotIn('su-consejo-fila', cuerpo)
        self.assertLess(cuerpo.index('data-consejos'), cuerpo.index('data-esfera-hoja'))
