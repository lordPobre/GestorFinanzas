from datetime import date
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from finanzas import diseno
from finanzas.servicios import indicadores


def _falso(codigo, anio):
    if anio != 2026:
        return []
    if codigo == 'utm':
        return [(date(2026, 10, 1), 69660.0), (date(2026, 11, 1), 69870.0)]
    return [(date(2026, 11, 6), 950.0), (date(2026, 11, 9), 948.0), (date(2026, 11, 12), 948.32)]


@mock.patch('finanzas.servicios.indicadores.fechas.hoy', return_value=date(2026, 11, 12))
class IndicadoresTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_rellena_los_dias_sin_valor(self, _hoy):
        with mock.patch.object(indicadores, '_pedir', side_effect=_falso):
            d = indicadores.datos()
        dolar = dict(d['series']['dolar'])
        self.assertEqual(dolar['2026-11-07'], 950.0)
        self.assertEqual(dolar['2026-11-12'], 948.32)
        self.assertEqual(d['series']['utm'][-1], ['2026-11-12', 69870.0])
        self.assertTrue(d['hay'])

    def test_guarda_una_hora_y_no_vuelve_a_pedir(self, _hoy):
        with mock.patch.object(indicadores, '_pedir', side_effect=_falso) as pedir:
            indicadores.datos()
            indicadores.datos()
        self.assertEqual(pedir.call_count, 8)

    def test_si_falla_usa_lo_ultimo_que_trajo(self, _hoy):
        with mock.patch.object(indicadores, '_pedir', side_effect=_falso):
            indicadores.datos()
        cache.delete(indicadores.CLAVE)
        with mock.patch.object(indicadores, '_pedir', side_effect=OSError('sin red')):
            d = indicadores.datos()
        self.assertEqual(d['series']['dolar'][-1][1], 948.32)

    def test_sin_red_y_sin_respaldo_no_se_cae(self, _hoy):
        with mock.patch.object(indicadores, '_pedir', side_effect=OSError('sin red')):
            d = indicadores.datos()
        self.assertFalse(d['hay'])


class VistaIndicadoresTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)

    def test_con_el_2c_muestra_la_pantalla(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        with mock.patch.object(indicadores, '_pedir', side_effect=_falso):
            r = self.client.get(reverse('indicadores'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="datosIndicadores"')
        self.assertContains(r, 'data-ind-lista')

    def test_sin_red_muestra_el_aviso(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        with mock.patch.object(indicadores, '_pedir', side_effect=OSError('sin red')):
            r = self.client.get(reverse('indicadores'))
        self.assertContains(r, 'No pudimos traer los indicadores')

    def test_sin_el_2c_vuelve_a_tu(self):
        r = self.client.get(reverse('indicadores'))
        self.assertRedirects(r, reverse('perfil'), fetch_redirect_response=False)

    def test_tu_tiene_el_enlace(self):
        self.client.cookies[diseno.COOKIE] = diseno.VALOR
        with mock.patch.object(indicadores, '_pedir', side_effect=_falso):
            self.assertContains(self.client.get(reverse('perfil')), reverse('indicadores'))
