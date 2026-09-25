import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from dateutil.relativedelta import relativedelta

from .. import legal
from ..almacenamiento import AlmacenMedia
from ..models import Deuda, Transaccion
from ..servicios import mes

EXTERNOS = ('fonts.googleapis.com', 'fonts.gstatic.com', 'cdnjs.cloudflare.com', 'cdn.jsdelivr.net')


class SinTercerosEnLasPaginas(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def _revisar(self, respuesta):
        cuerpo = respuesta.content.decode('utf-8')
        politica = respuesta.get('Content-Security-Policy', '')
        for dominio in EXTERNOS:
            self.assertNotIn(dominio, cuerpo)
            self.assertNotIn(dominio, politica)

    def test_el_acceso(self):
        self._revisar(self.client.get(reverse('login')))

    def test_las_paginas_legales(self):
        self._revisar(self.client.get(reverse('privacidad')))

    def test_el_panel_con_graficos(self):
        self.client.force_login(self.ana)
        self._revisar(self.client.get(reverse('dashboard')))
        self._revisar(self.client.get(reverse('estadisticas')))


class PoliticaVigente(TestCase):
    def test_declara_lo_nuevo(self):
        cuerpo = self.client.get(reverse('privacidad')).content.decode('utf-8')
        self.assertIn(legal.VERSION, cuerpo)
        for texto in ('Face ID', 'encuesta', 'Registro de seguridad', 'Copias de respaldo'):
            self.assertIn(texto, cuerpo)
        self.assertNotIn('Google Fonts', cuerpo)


class FotosPrivadas(TestCase):
    R2 = {'R2_ACCESS_KEY_ID': 'clave', 'R2_SECRET_ACCESS_KEY': 'secreto', 'R2_BUCKET': 'fotos',
          'R2_ENDPOINT_URL': 'https://cuenta.r2.cloudflarestorage.com', 'R2_PUBLIC_DOMAIN': 'fotos.ejemplo.cl'}

    def test_las_urls_van_firmadas_y_sin_dominio_publico(self):
        with patch.dict(os.environ, self.R2):
            almacen = AlmacenMedia()
            almacen._setup()
            destino = almacen._wrapped
        self.assertTrue(destino.querystring_auth)
        self.assertIsNone(destino.custom_domain)
        with patch.dict(os.environ, self.R2):
            url = destino.url('avatares/1/foto.jpg')
        self.assertIn('X-Amz-Signature', url)
        self.assertNotIn('fotos.ejemplo.cl', url)


class MesesCerradosEnCache(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', password='x')
        self.pasado = date.today().replace(day=1) - relativedelta(months=2)

    def _gasto(self, monto, fecha=None):
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(monto),
                                   categoria='Comida', fecha=fecha or self.pasado.replace(day=10))

    def test_la_segunda_vez_no_recalcula(self):
        self._gasto('1000')
        with patch('finanzas.servicios.mes.resumen_mes', wraps=mes.resumen_mes) as calculo:
            mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)
            mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)
        self.assertEqual(calculo.call_count, 1)

    def test_un_movimiento_nuevo_invalida_la_cache(self):
        self._gasto('1000')
        antes = mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)
        self._gasto('500')
        despues = mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)
        self.assertEqual(antes['gastos'], 1000)
        self.assertEqual(despues['gastos'], 1500)

    def test_borrar_un_movimiento_invalida_la_cache(self):
        self._gasto('1000')
        mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)
        Transaccion.objects.filter(usuario=self.ana).delete()
        self.assertEqual(mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)['gastos'], 0)

    def test_una_compra_en_cuotas_nueva_invalida_la_cache(self):
        mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)
        Deuda.objects.create(usuario=self.ana, acreedor='Tienda', monto_total=Decimal('60000'),
                             cuotas_totales=6, fecha_inicio=self.pasado)
        self.assertGreater(mes.numeros_mes(self.ana, self.pasado.year, self.pasado.month)['total_cuotas_mes'], 0)

    def test_el_mes_en_curso_nunca_sale_de_la_cache(self):
        hoy = date.today()
        with patch('finanzas.servicios.mes.resumen_mes', wraps=mes.resumen_mes) as calculo:
            mes.numeros_mes(self.ana, hoy.year, hoy.month)
            mes.numeros_mes(self.ana, hoy.year, hoy.month)
        self.assertEqual(calculo.call_count, 2)

    def test_la_cache_es_de_cada_usuario(self):
        beto = User.objects.create_user('beto', password='x')
        self._gasto('1000')
        self.assertEqual(mes.numeros_mes(beto, self.pasado.year, self.pasado.month)['gastos'], 0)
