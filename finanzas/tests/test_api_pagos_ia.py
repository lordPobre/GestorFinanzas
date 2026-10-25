import json
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .. import fechas
from ..models import Deuda, PagoCuota, Transaccion, UserProfile
from ..views.api import nueva_clave


def _falso(entrada):
    respuesta = SimpleNamespace(stop_reason='tool_use', usage=None,
                                content=[SimpleNamespace(type='tool_use', id='t1', name='anotar', input=entrada)])
    return SimpleNamespace(messages=SimpleNamespace(create=mock.Mock(return_value=respuesta)))


class ApiPagosTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(usuario=self.ana,
                                                              defaults={'onboarding_completado': True})
        self.clave = nueva_clave(self.ana)
        self.deuda = Deuda.objects.create(usuario=self.ana, acreedor='Notebook', monto_total=Decimal('120000'),
                                          cuotas_totales=12, fecha_inicio=fechas.hoy().replace(day=1))

    def _pagar(self, tipo, objeto_id, clave=None):
        return self.client.post(f'/api/v1/pagos/{tipo}/{objeto_id}/', '{}', content_type='application/json',
                                HTTP_AUTHORIZATION=f'Bearer {clave or self.clave}')

    def test_marca_la_cuota_una_sola_vez(self):
        r = self._pagar('cuota', self.deuda.pk)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['ok'])
        self.assertEqual(PagoCuota.objects.filter(deuda=self.deuda).count(), 1)

    def test_no_paga_lo_de_otra_persona(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        r = self._pagar('cuota', self.deuda.pk, nueva_clave(beto))
        self.assertEqual(r.status_code, 404)
        self.assertFalse(PagoCuota.objects.exists())

    def test_tipo_que_no_existe(self):
        self.assertEqual(self._pagar('hipoteca', 1).status_code, 404)

    def test_sin_clave(self):
        r = self.client.post(reverse('api_pago_cuota', args=[self.deuda.pk]))
        self.assertEqual(r.status_code, 401)


class ApiConIaTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'onboarding_completado': True, 'analisis_ia': True})
        self.clave = nueva_clave(self.ana)

    def _post(self, texto):
        return self.client.post(reverse('api_movimientos'), json.dumps({'texto': texto}),
                                content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {self.clave}')

    def test_si_las_reglas_no_alcanzan_usa_haiku(self):
        falso = _falso({'monto': 5000, 'descripcion': 'café', 'tipo': 'EGRESO', 'dias_atras': 0})
        with mock.patch('finanzas.ia_cliente.cliente', return_value=falso):
            r = self._post('un café de cinco mil')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Transaccion.objects.get().monto, Decimal('5000'))
        enviado = falso.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertIn('un café de cinco mil', enviado)

    def test_si_las_reglas_alcanzan_no_llama_a_la_ia(self):
        with mock.patch('finanzas.ia_cliente.cliente') as cliente:
            self.assertEqual(self._post('5 lucas café').status_code, 201)
        cliente.assert_not_called()

    def test_sin_ia_activada_no_llama(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])
        with mock.patch('finanzas.ia_cliente.cliente') as cliente:
            self.assertEqual(self._post('un café de cinco mil').status_code, 400)
        cliente.assert_not_called()

    def test_si_haiku_tampoco_encuentra_monto(self):
        falso = _falso({'monto': 0, 'descripcion': '', 'tipo': 'EGRESO', 'dias_atras': 0})
        with mock.patch('finanzas.ia_cliente.cliente', return_value=falso):
            self.assertEqual(self._post('hola').status_code, 400)
