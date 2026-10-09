from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..servicios.mes_elegido import selector_mes


class MesEnElTituloTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def test_el_nombre_corto_cabe_junto_al_titulo(self):
        sel = selector_mes(self.ana, 2026, 9, date(2026, 10, 9))
        self.assertEqual(sel['corto'], 'Sep 2026')

    def test_el_boton_del_telefono_va_dentro_del_encabezado(self):
        self.client.force_login(self.ana)
        for nombre in ('categorias', 'estadisticas'):
            html = self.client.get(reverse(nombre)).content.decode()
            cabeza = html[html.index('class="sec-top"'):html.index('</div>', html.index('class="mes-tel"'))]
            self.assertIn('class="mes-tel"', cabeza, nombre)
