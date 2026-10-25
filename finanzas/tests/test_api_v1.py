import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .. import fechas
from ..models import ClaveApi, Transaccion, UserProfile
from ..servicios.anotar_texto import interpretar
from ..views.api import nueva_clave


class InterpretarTextoTests(SimpleTestCase):

    def test_lucas_y_descripcion(self):
        r = interpretar('5 lucas en café')
        self.assertEqual(r['monto'], Decimal('5000'))
        self.assertEqual(r['descripcion'], 'Café')
        self.assertEqual(r['tipo'], 'EGRESO')

    def test_monto_con_puntos(self):
        r = interpretar('12.990 Netflix')
        self.assertEqual(r['monto'], Decimal('12990'))
        self.assertEqual(r['descripcion'], 'Netflix')

    def test_ayer(self):
        r = interpretar('ayer 8000 uber')
        self.assertEqual(r['fecha'], fechas.hoy() - timedelta(days=1))
        self.assertEqual(r['monto'], Decimal('8000'))
        self.assertEqual(r['descripcion'], 'Uber')

    def test_ingreso(self):
        self.assertEqual(interpretar('me pagaron 500 lucas')['tipo'], 'INGRESO')

    def test_sin_monto(self):
        r = interpretar('café')
        self.assertFalse(r['claro'])
        self.assertIsNone(r['monto'])


class ApiTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.update_or_create(usuario=self.ana, defaults={'onboarding_completado': True})
        self.clave = nueva_clave(self.ana)

    def _post(self, datos, clave=None):
        return self.client.post(reverse('api_movimientos'), json.dumps(datos), content_type='application/json',
                                HTTP_AUTHORIZATION=f'Bearer {clave or self.clave}')

    def test_anota_texto_libre(self):
        r = self._post({'texto': '5 lucas en café'})
        self.assertEqual(r.status_code, 201)
        d = r.json()
        self.assertTrue(d['texto'].startswith('Anotado: $5.000 en '))
        tx = Transaccion.objects.get(pk=d['id'])
        self.assertEqual(tx.usuario, self.ana)
        self.assertEqual(tx.origen, Transaccion.API)
        self.assertTrue(tx.pagado)

    def test_anota_por_campos(self):
        r = self._post({'monto': '1500', 'descripcion': 'pan', 'tipo': 'EGRESO'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['descripcion'], 'Pan')

    def test_sin_monto_responde_400(self):
        r = self._post({'texto': 'café'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'monto')
        self.assertFalse(Transaccion.objects.exists())

    def test_sin_clave_o_revocada(self):
        r = self.client.post(reverse('api_movimientos'), '{}', content_type='application/json')
        self.assertEqual(r.status_code, 401)
        ClaveApi.objects.all().delete()
        self.assertEqual(self._post({'texto': '5 lucas café'}).status_code, 401)

    def test_no_pide_csrf_ni_sesion(self):
        self.client.logout()
        self.assertEqual(self._post({'texto': '2000 bus'}).status_code, 201)

    def test_la_clave_se_guarda_como_huella(self):
        fila = ClaveApi.objects.get(usuario=self.ana)
        self.assertNotEqual(fila.huella, self.clave)
        self.assertNotIn(self.clave, fila.huella)
        self.assertEqual(fila.prefijo, self.clave[:8])

    def test_deshacer_solo_lo_propio_y_reciente(self):
        tx_id = self._post({'texto': '3000 café'}).json()['id']
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        clave_beto = nueva_clave(beto)
        url = reverse('api_movimiento', args=[tx_id])
        self.assertEqual(self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {clave_beto}').status_code, 404)
        self.assertEqual(self.client.delete(url, HTTP_AUTHORIZATION=f'Bearer {self.clave}').status_code, 200)
        self.assertFalse(Transaccion.objects.filter(pk=tx_id).exists())

    def test_no_deshace_lo_anotado_a_mano(self):
        tx = Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('1000'), categoria='Otros',
                                        fecha=fechas.hoy())
        r = self.client.delete(reverse('api_movimiento', args=[tx.pk]), HTTP_AUTHORIZATION=f'Bearer {self.clave}')
        self.assertEqual(r.status_code, 404)


class PaginaClaveTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.update_or_create(usuario=self.ana, defaults={'onboarding_completado': True})
        self.client.force_login(self.ana)

    def test_crear_muestra_la_clave_una_vez_y_revocar_la_borra(self):
        r = self.client.post(reverse('clave_api'), {'accion': 'crear'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-clave-nueva')
        self.assertEqual(r['Cache-Control'], 'no-store')
        self.assertTrue(ClaveApi.objects.filter(usuario=self.ana).exists())
        self.assertNotContains(self.client.get(reverse('clave_api')), 'data-clave-nueva')
        self.client.post(reverse('clave_api'), {'accion': 'revocar'})
        self.assertFalse(ClaveApi.objects.filter(usuario=self.ana).exists())
