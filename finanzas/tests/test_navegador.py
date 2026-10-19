import os
import unittest
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse

from .. import legal
from ..models import Deuda, PagoCuota, Transaccion, UserProfile

ACTIVAS = os.environ.get('PRUEBAS_NAVEGADOR') == '1'

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

SIN_TOUR = """
try {
  localStorage.setItem('finapp.tour.listo', '1');
  localStorage.setItem('finapp.tour.version', '4');
  localStorage.setItem('finapp.pasos.oculto', '1');
} catch (e) {}
"""

IPHONE = {
    'viewport': {'width': 390, 'height': 844},
    'device_scale_factor': 3,
    'is_mobile': True,
    'has_touch': True,
    'user_agent': ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 '
                   '(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'),
}
ESCRITORIO = {'viewport': {'width': 1280, 'height': 900}}


@unittest.skipUnless(ACTIVAS and sync_playwright, 'Pruebas en navegador: PRUEBAS_NAVEGADOR=1 y playwright')
class NavegadorTests(StaticLiveServerTestCase):
    host = 'localhost'

    @classmethod
    def setUpClass(cls):
        os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
        super().setUpClass()
        cls.pw = sync_playwright().start()
        cls.navegador = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.navegador.close()
        cls.pw.stop()
        super().tearDownClass()

    def setUp(self):
        self.clave = 'clave-larga-de-prueba-1'
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', self.clave)
        perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        perfil.politica_version = legal.VERSION
        perfil.save()

    def _pagina(self, aparato, con_sesion=False):
        contexto = self.navegador.new_context(service_workers='block', locale='es-CL', **aparato)
        contexto.add_init_script(SIN_TOUR)
        if con_sesion:
            cliente = Client()
            cliente.force_login(self.ana)
            contexto.add_cookies([{
                'name': settings.SESSION_COOKIE_NAME,
                'value': cliente.cookies[settings.SESSION_COOKIE_NAME].value,
                'url': self.live_server_url,
            }])
        self.addCleanup(contexto.close)
        pagina = contexto.new_page()
        pagina.set_default_timeout(10000)
        return pagina

    def _ruta(self, pagina):
        return urlparse(pagina.url).path

    def _esperar(self, pagina, condicion, segundos=10):
        for _ in range(segundos * 10):
            if condicion():
                return True
            pagina.wait_for_timeout(100)
        return condicion()

    def test_entrar_en_el_computador(self):
        p = self._pagina(ESCRITORIO)
        p.goto(self.live_server_url + reverse('login'))
        self.assertFalse(p.locator('.lm-hero').is_visible())
        p.fill('input[name=username]', 'ana')
        p.fill('input[name=password]', self.clave)
        p.click('#btnEntrar')
        p.wait_for_url(lambda url: urlparse(url).path == reverse('dashboard'))
        self.assertEqual(self._ruta(p), reverse('dashboard'))

    def test_entrar_en_el_telefono_con_la_hoja(self):
        p = self._pagina(IPHONE)
        p.goto(self.live_server_url + reverse('login'))
        self.assertTrue(p.locator('.lm-hero').is_visible())
        self.assertEqual(p.locator('.auth.lm.abierto').count(), 0)
        p.click('[data-lm-abrir]')
        p.wait_for_selector('.auth.lm.abierto')
        self.assertTrue(self._esperar(p, lambda: p.locator('.auth-panel').bounding_box()['y'] < 844 / 2))
        p.fill('input[name=username]', 'ana')
        p.fill('input[name=password]', self.clave)
        p.click('#btnEntrar')
        p.wait_for_url(lambda url: urlparse(url).path == reverse('dashboard'))
        self.assertEqual(self._ruta(p), reverse('dashboard'))

    def test_la_hoja_se_cierra_y_vuelve_la_esfera(self):
        p = self._pagina(IPHONE)
        p.goto(self.live_server_url + reverse('login'))
        p.click('[data-lm-abrir]')
        p.wait_for_selector('.auth.lm.abierto')
        p.click('.lm-cerrar')
        p.wait_for_selector('.auth.lm:not(.abierto)')
        self.assertTrue(p.locator('[data-lm-abrir]').is_visible())

    def test_anotar_un_gasto(self):
        p = self._pagina(ESCRITORIO, con_sesion=True)
        p.goto(self.live_server_url + reverse('dashboard') + '?registrar=1')
        p.wait_for_selector('#modalGasto.open')
        for tecla in ('1', '2', '000'):
            p.click(f'#modalGasto [data-keypad] [data-key="{tecla}"]')
        p.fill('#campoDesc', 'Almuerzo de prueba')
        p.click('#btnGuardar')
        hay = lambda: Transaccion.objects.filter(usuario=self.ana, descripcion='Almuerzo de prueba').exists()
        self.assertTrue(self._esperar(p, hay))
        gasto = Transaccion.objects.get(usuario=self.ana, descripcion='Almuerzo de prueba')
        self.assertEqual((gasto.tipo, gasto.monto), ('EGRESO', Decimal('12000')))

    def test_pagar_una_cuota(self):
        deuda = Deuda.objects.create(usuario=self.ana, acreedor='Tienda de prueba',
                                     monto_total=Decimal('300000'), cuotas_totales=3,
                                     fecha_inicio=date.today().replace(day=1) - relativedelta(months=1))
        p = self._pagina(ESCRITORIO, con_sesion=True)
        p.goto(self.live_server_url + reverse('deudas'))
        boton = p.locator(f'form[action="{reverse("pagar_cuota", args=[deuda.pk])}"] button[type=submit]:visible').first
        boton.click()
        self.assertTrue(self._esperar(p, lambda: PagoCuota.objects.filter(deuda=deuda).exists()))
        p.wait_for_timeout(500)
        self.assertEqual(PagoCuota.objects.filter(deuda=deuda).count(), 1)
