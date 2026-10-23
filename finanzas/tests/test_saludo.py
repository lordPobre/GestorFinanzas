from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse


class SaludoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _html(self, nombre):
        return self.client.get(reverse(nombre)).content.decode()

    def test_inicio_no_lleva_la_tarjeta_del_saludo(self):
        html = self._html('dashboard')
        self.assertNotIn('class="saludo-card"', html)
        self.assertIn('class="topbar-campana"', html)
        self.assertIn('class="ini-top-campana"', html)

    def test_las_pantallas_con_titulo_no_la_llevan(self):
        for nombre in ('metas', 'perfil', 'deudas', 'por_pagar'):
            with self.subTest(nombre):
                self.assertNotIn('class="saludo-card"', self._html(nombre))

    def test_la_encuesta_si_la_lleva(self):
        html = self._html('encuesta')
        self.assertEqual(html.count('class="saludo-card"'), 1)
        self.assertIn('<button type="button" class="saludo-campana"', html)

    def test_las_campanas_avisan_por_lo_mismo(self):
        for avisos in ({'cuotas_atrasadas': 1}, {'pendientes_sin_pagar': [1]}, {'insights': [1]},
                       {'atrasado_arrastrado': 1}):
            with self.subTest(avisos):
                self.assertIn('class="punto"', render_to_string('finanzas/_campana.html', {'clase': 'x', **avisos}))
        self.assertNotIn('class="punto"', render_to_string('finanzas/_campana.html', {'clase': 'x'}))
