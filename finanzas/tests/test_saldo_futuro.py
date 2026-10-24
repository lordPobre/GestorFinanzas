from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .. import fechas
from ..models import Deuda, Transaccion, UserProfile


class SaldoFuturoTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.update_or_create(usuario=self.ana, defaults={'onboarding_completado': True})
        self.client.force_login(self.ana)
        self.hoy = fechas.hoy()
        self.primero = self.hoy.replace(day=1)

    def _historia(self):
        for atras in (1, 2, 3):
            f = (self.primero - relativedelta(months=atras)).replace(day=10)
            Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000000'),
                                       categoria='Sueldo', fecha=f)
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('400000'),
                                       categoria='Comida', fecha=f, pagado=True)
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000000'),
                                   categoria='Sueldo', fecha=self.primero)
        Deuda.objects.create(usuario=self.ana, acreedor='Notebook Lenovo', monto_total=Decimal('120000'),
                             cuotas_totales=12, fecha_inicio=self.primero.replace(day=28))

    def _pedir(self):
        return self.client.get(reverse('inicio_proyeccion'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_entrega_la_linea_del_mes_y_los_tres_que_vienen(self):
        self._historia()
        r = self._pedir()
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(len(d['meses']), 3)
        self.assertEqual(sum(1 for m in d['meses'] if m['justo']), 1)
        self.assertEqual(d['dias'][0]['s'] <= d['inicio'], True)
        self.assertTrue(d['fin'].startswith('$'))
        for m in d['meses']:
            self.assertTrue(0 <= m['pct'] <= 100)
            self.assertEqual(len(m['corto']), 3)

    def test_los_cobros_que_faltan_llevan_nombre_y_monto(self):
        self._historia()
        d = self._pedir().json()
        if self.hoy.day <= 28:
            self.assertIn('Notebook Lenovo', [c['nombre'] for c in d['cobros']])
            self.assertTrue(any(dia['cobro'] for dia in d['dias']))

    def test_sin_historia_no_hay_tarjeta(self):
        self.assertEqual(self._pedir().json(), {'ok': False})

    def test_inicio_trae_la_tarjeta_solo_en_el_mes_actual(self):
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, 'data-saldo-futuro')
        self.assertContains(r, f'data-url="{reverse("inicio_proyeccion")}"')
        self.assertContains(r, 'js/pantallas/saldo-futuro.js')
        self.assertContains(r, 'id="modalSaldoFuturo"')
        pasado = self.primero - timedelta(days=1)
        r = self.client.get(reverse('dashboard'), {'year': pasado.year, 'month': pasado.month})
        self.assertNotContains(r, 'data-saldo-futuro')

    def test_pide_sesion(self):
        self.client.logout()
        self.assertEqual(self._pedir().status_code, 302)
