from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AnotarEnUnPasoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def _html(self):
        return self.client.get(reverse('categorias')).content.decode()

    def test_los_botones_anotar_abren_directo_el_registro_de_gasto(self):
        html = self._html()
        for clase in ('class="sidebar-anotar"', 'class="nav-item nav-anotar"'):
            inicio = html.index(clase)
            boton = html[inicio:html.index('>', inicio)]
            self.assertIn('data-open="#modalGasto"', boton, clase)
            self.assertIn('data-preset-tipo="EGRESO"', boton, clase)
        self.assertNotIn('data-open="#modalAnotar"', html)

    def test_la_cartola_sigue_a_mano_al_anotar(self):
        html = self._html()
        inicio = html.index('class="anotar-atajos"')
        self.assertIn(reverse('importar_cartola'), html[inicio:html.index('</div>', inicio)])
