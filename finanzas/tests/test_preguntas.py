import json
import os
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .. import fechas, legal
from ..models import Deuda, UserProfile
from ..ia_preguntas import MAX_TURNOS

CLAVE = {'ANTHROPIC_API_KEY': 'k'}


def _uso(nombre, entrada=None):
    return SimpleNamespace(stop_reason='tool_use', usage=None,
                           content=[SimpleNamespace(type='tool_use', id='t1', name=nombre, input=entrada or {})])


def _texto(texto):
    return SimpleNamespace(stop_reason='end_turn', usage=None, content=[SimpleNamespace(type='text', text=texto)])


class PreguntasTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'onboarding_completado': True, 'analisis_ia': True,
                                        'politica_version': legal.VERSION})
        hoy = fechas.hoy()
        from decimal import Decimal
        Deuda.objects.create(usuario=self.ana, acreedor='Notebook Lenovo', monto_total=Decimal('120000'),
                             cuotas_totales=12, fecha_inicio=hoy.replace(day=1))
        self.client.force_login(self.ana)

    def _preguntar(self, respuestas, pregunta='¿Cuándo termino el notebook?', conversacion=''):
        crear = mock.Mock(side_effect=respuestas)
        falso = SimpleNamespace(messages=SimpleNamespace(create=crear))
        with mock.patch.dict(os.environ, CLAVE), mock.patch('finanzas.ia_cliente.cliente', return_value=falso):
            r = self.client.post(reverse('esfera_preguntar'),
                                 {'pregunta': pregunta, 'conversacion': conversacion})
        return r, crear

    def test_responde_con_herramientas_y_nombres_restaurados(self):
        r, crear = self._preguntar([_uso('fin_deuda'), _texto('Deuda 1 termina en el último mes.')])
        datos = r.json()
        self.assertTrue(datos['ok'])
        self.assertIn('Notebook Lenovo', datos['texto'])
        self.assertEqual(datos['turno'], 1)
        self.assertEqual(datos['quedan'], MAX_TURNOS - 1)
        enviado = json.dumps([c.kwargs['messages'] for c in crear.call_args_list], ensure_ascii=False, default=str)
        self.assertNotIn('Notebook', enviado.replace('¿Cuándo termino el notebook?', ''))
        self.assertEqual(crear.call_args_list[1].kwargs['messages'][-1]['content'][0]['type'], 'tool_result')

    def test_la_conversacion_sigue_y_se_corta_en_cuatro(self):
        r, _ = self._preguntar([_texto('Primera.')])
        cid = r.json()['conversacion']
        for n in range(2, MAX_TURNOS + 1):
            r, crear = self._preguntar([_texto(f'Respuesta {n}.')], conversacion=cid)
            self.assertEqual(r.json()['turno'], n)
        mensajes = crear.call_args.kwargs['messages']
        self.assertEqual(len(mensajes), 2 * (MAX_TURNOS - 1) + 1)
        r, _ = self._preguntar([_texto('Sobra.')], conversacion=cid)
        self.assertEqual(r.json()['motivo'], 'conversacion')

    @mock.patch.dict(os.environ, {'PREGUNTAS_TOPE_DIA': '3'})
    def test_tope_diario(self):
        for _ in range(3):
            self._preguntar([_texto('Ok.')])
        r, crear = self._preguntar([_texto('No debería.')])
        self.assertEqual(r.json()['motivo'], 'tope')
        crear.assert_not_called()

    def test_pide_la_politica_vigente_y_la_ia_activada(self):
        self.perfil.politica_version = '1.8'
        self.perfil.save(update_fields=['politica_version'])
        r, _ = self._preguntar([_texto('Ok.')])
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['motivo'], 'politica')
        self.perfil.politica_version = legal.VERSION
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['politica_version', 'analisis_ia'])
        r, _ = self._preguntar([_texto('Ok.')])
        self.assertEqual(r.json()['motivo'], 'desactivado')

    def test_pregunta_vacia(self):
        r, _ = self._preguntar([], pregunta='   ')
        self.assertEqual(r.status_code, 400)

    def test_sin_clave_no_hay_respuesta(self):
        with mock.patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''}):
            r = self.client.post(reverse('esfera_preguntar'), {'pregunta': 'Hola'})
        self.assertFalse(r.json()['ok'])

    def test_si_la_ia_no_deja_de_pedir_herramientas_no_responde(self):
        r, crear = self._preguntar([_uso('queda_mes')] * 6)
        self.assertFalse(r.json()['ok'])
        self.assertEqual(crear.call_count, 5)

    def test_solo_post(self):
        self.assertEqual(self.client.get(reverse('esfera_preguntar')).status_code, 405)
