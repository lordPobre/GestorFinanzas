from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from ..cartolas.base import Cartola, ErrorCartola, MovimientoLeido
from ..models import UserProfile
from ..servicios import lectura_cartola

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def _cartola():
    return Cartola(banco='Banco de prueba', movimientos=[MovimientoLeido(
        fecha=date(2026, 10, 3), descripcion='Café del centro', monto=Decimal('3500'),
        tipo='EGRESO', saldo=Decimal('0'))])


class CartolaEnSegundoPlanoTests(TestCase):

    def setUp(self):
        cache.clear()
        sincronica = mock.patch('finanzas.cola.sincronica', return_value=True)
        sincronica.start()
        self.addCleanup(sincronica.stop)
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.update_or_create(usuario=self.ana, defaults={'onboarding_completado': True})
        self.client.force_login(self.ana)

    def _subir(self, **extra):
        archivo = SimpleUploadedFile('cartola.pdf', b'%PDF-1.4 prueba', content_type='application/pdf')
        return self.client.post(reverse('importar_cartola'), {'cartola': archivo, 'banco': ''}, **extra)

    def _tarea(self, firmado):
        return self.client.get(reverse('tarea_cartola'), {'t': firmado}, **AJAX)

    @mock.patch('finanzas.cartolas.leer_cartola', side_effect=lambda *a, **k: _cartola())
    def test_devuelve_una_tarea_y_al_terminar_pasa_a_revisar(self, leer):
        r = self._subir(**AJAX)
        self.assertEqual(r.status_code, 200)
        firmado = r.json()['tarea']
        r = self._tarea(firmado)
        self.assertEqual(r.json(), {'listo': True, 'url': reverse('revisar_cartola')})
        movimientos = self.client.session['cartola_pendiente']['movimientos']
        self.assertEqual(movimientos[0]['descripcion'], 'Café del centro')
        self.assertEqual(self.client.get(reverse('revisar_cartola')).status_code, 200)
        self.assertEqual(leer.call_args.args[0].read(), b'%PDF-1.4 prueba')

    @mock.patch('finanzas.cartolas.leer_cartola', side_effect=lambda *a, **k: _cartola())
    def test_no_queda_nada_guardado_al_entregar(self, leer):
        from django_q.models import OrmQ, Task

        firmado = self._subir(**AJAX).json()['tarea']
        self._tarea(firmado)
        numero = signing.loads(firmado, salt=lectura_cartola.SAL)['n']
        self.assertIsNone(cache.get(lectura_cartola._clave(self.ana.pk, numero)))
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(OrmQ.objects.count(), 0)

    def test_si_no_se_puede_leer_vuelve_con_el_motivo_y_la_muestra(self):
        error = ErrorCartola('No reconocí el formato de esta cartola.')
        error.muestra = 'XXXX 99/99 9.999'
        with mock.patch('finanzas.cartolas.leer_cartola', side_effect=error):
            firmado = self._subir(**AJAX).json()['tarea']
        r = self._tarea(firmado)
        self.assertEqual(r.json()['url'], reverse('importar_cartola'))
        diagnostico = self.client.session['cartola_diagnostico']
        self.assertEqual(diagnostico['texto'], 'XXXX 99/99 9.999')
        self.assertEqual(diagnostico['archivo'], 'cartola.pdf')

    @mock.patch('finanzas.cartolas.leer_cartola', side_effect=lambda *a, **k: _cartola())
    def test_la_tarea_de_otra_persona_no_se_entrega(self, leer):
        firmado = self._subir(**AJAX).json()['tarea']
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self.client.force_login(beto)
        self.assertEqual(self._tarea(firmado).status_code, 404)
        self.assertEqual(self._tarea('cualquier-cosa').status_code, 404)

    @mock.patch('finanzas.cartolas.leer_cartola', side_effect=lambda *a, **k: _cartola())
    def test_sin_javascript_sigue_como_antes(self, leer):
        r = self._subir()
        self.assertRedirects(r, reverse('revisar_cartola'), fetch_redirect_response=False)
        self.assertIn('cartola_pendiente', self.client.session)

    def test_con_todos_los_cupos_ocupados_pide_esperar(self):
        for _ in range(lectura_cartola.MAX_A_LA_VEZ):
            lectura_cartola._cupos.acquire()
        try:
            r = self._subir(**AJAX)
        finally:
            for _ in range(lectura_cartola.MAX_A_LA_VEZ):
                lectura_cartola._cupos.release()
        self.assertEqual(r.status_code, 503)
        self.assertIn('minuto', r.json()['msg'])

    def test_la_pantalla_trae_la_ruta_de_la_tarea(self):
        r = self.client.get(reverse('importar_cartola'))
        self.assertContains(r, f'data-url-tarea="{reverse("tarea_cartola")}"')
