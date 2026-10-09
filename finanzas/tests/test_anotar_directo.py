from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AnotarEnUnPasoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_el_boton_mas_abre_directo_el_registro_de_gasto(self):
        html = self.client.get(reverse('categorias')).content.decode()
        inicio = html.index('class="fab"')
        boton = html[inicio:html.index('>', inicio)]
        self.assertIn('data-open="#modalGasto"', boton)
        self.assertIn('data-preset-tipo="EGRESO"', boton)
        self.assertNotIn('data-open="#modalAnotar"', html)

    def test_la_cartola_sigue_a_mano_en_la_hoja_mas(self):
        html = self.client.get(reverse('categorias')).content.decode()
        mas = html[html.index('id="modalMas"'):]
        self.assertIn(reverse('importar_cartola'), mas[:mas.index('id="modalAnotar"')])
