from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from ..models import Transaccion


class MovimientosInicioTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.hoy = date.today()
        self.sueldo = Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('900000'),
                                                 categoria='Sueldo', fecha=self.hoy, descripcion='Sueldo')
        self.pan = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('2500'),
                                              categoria='Otros', fecha=self.hoy, descripcion='Pan')

    def _movimientos(self, **params):
        return self.client.get(reverse('inicio_movimientos'), params)

    def test_inicio_deja_la_lista_para_cuando_se_abre(self):
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('id="modalMovimientos"', html)
        self.assertIn(f'data-fragmento="{reverse("inicio_movimientos")}?year={self.hoy.year}&amp;month={self.hoy.month}"', html)
        self.assertNotIn('swipe-mov', html)
        self.assertNotIn(reverse('eliminar_transaccion', args=[self.pan.pk]), html)

    def test_la_lista_trae_los_movimientos_del_mes(self):
        respuesta = self._movimientos(year=self.hoy.year, month=self.hoy.month)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'no-store')
        html = respuesta.content.decode()
        self.assertIn('data-movimientos-caja', html)
        self.assertIn('swipe-mov', html)
        self.assertIn('Pan', html)
        self.assertIn('Sueldo', html)
        self.assertIn('data-mov-filtro="ingreso"', html)
        self.assertIn(reverse('eliminar_transaccion', args=[self.pan.pk]), html)
        self.assertNotIn('<html', html)

    def test_al_volver_queda_en_el_mismo_mes(self):
        html = self._movimientos(year=self.hoy.year, month=self.hoy.month).content.decode()
        self.assertIn(f'value="{reverse("dashboard")}?year={self.hoy.year}&amp;month={self.hoy.month}"', html)
        self.assertNotIn(f'value="{reverse("inicio_movimientos")}', html)

    def test_otro_mes_no_trae_los_de_este(self):
        antes = self.hoy.replace(day=1) - relativedelta(months=1)
        html = self._movimientos(year=antes.year, month=antes.month).content.decode()
        self.assertNotIn('swipe-mov', html)
        self.assertIn('Todavía no registras nada este mes', html)

    def test_un_mes_invalido_muestra_el_actual(self):
        html = self._movimientos(year='x', month='13').content.decode()
        self.assertIn('Pan', html)

    def test_no_muestra_lo_de_otra_persona(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        Transaccion.objects.create(usuario=beto, tipo='EGRESO', monto=Decimal('1000'),
                                   categoria='Otros', fecha=self.hoy, descripcion='Ajeno')
        self.assertNotIn('Ajeno', self._movimientos().content.decode())

    def test_sin_sesion_pide_entrar(self):
        self.client.logout()
        respuesta = self._movimientos()
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])
