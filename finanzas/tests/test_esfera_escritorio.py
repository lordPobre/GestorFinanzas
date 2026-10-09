from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Transaccion, UserProfile


class EsferaEnEscritorioTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        perfil.analisis_ia = True
        perfil.save()
        self.client.force_login(self.ana)
        self.hoy = date.today()
        self.antes = self.hoy.replace(day=1) - relativedelta(months=1)

    def _mes(self, fecha, ingreso, gasto):
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal(ingreso),
                                   categoria='Sueldo', fecha=fecha)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(gasto),
                                   categoria='Comida', fecha=fecha)

    def _estado_del_menu(self, html):
        inicio = html.index('class="sidebar-foot health"')
        trozo = html[inicio:html.index('>', inicio)]
        return trozo.split('data-estado="')[1].split('"')[0]

    def test_el_color_del_menu_sigue_al_mes_elegido(self):
        self._mes(self.hoy.replace(day=1), '1000000', '100000')
        self._mes(self.antes, '1000000', '1200000')
        actual = self.client.get(reverse('dashboard')).content.decode()
        pasado = self.client.get(reverse('dashboard'), {'year': self.antes.year, 'month': self.antes.month}).content.decode()
        self.assertEqual(self._estado_del_menu(actual), 'verde')
        self.assertEqual(self._estado_del_menu(pasado), 'rojo')

    def test_las_otras_pantallas_muestran_el_mes_actual(self):
        self._mes(self.hoy.replace(day=1), '1000000', '900000')
        html = self.client.get(reverse('metas')).content.decode()
        self.assertEqual(self._estado_del_menu(html), 'amarillo')

    def test_la_base_carga_la_voz_de_escritorio(self):
        self.assertContains(self.client.get(reverse('dashboard')), 'js/pantallas/esfera-escritorio.js')
