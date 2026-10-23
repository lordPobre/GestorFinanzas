import os
import re
import sys
import unittest
from collections import Counter
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import Deuda, PagoCuota, Transaccion

MEDIR = os.environ.get('MEDIR_INICIO') == '1'
TABLA = re.compile(r'FROM "(\w+)"')


def tablas(consultas):
    return Counter(t for q in consultas for t in TABLA.findall(q['sql']))


class ConsultasInicioTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.inicio = date.today().replace(day=1) - relativedelta(months=2)
        self.creadas = 0

    def _compras(self, n):
        for _ in range(n):
            self.creadas += 1
            deuda = Deuda.objects.create(usuario=self.ana, acreedor=f'Compra {self.creadas}',
                                         monto_total=Decimal('120000'), cuotas_totales=12,
                                         fecha_inicio=self.inicio)
            PagoCuota.objects.create(deuda=deuda, periodo=Deuda.periodo_de(self.inicio.year, self.inicio.month),
                                     monto=Decimal('10000'), fecha_pago=self.inicio)

    def _medir(self):
        cache.clear()
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta, consultas.captured_queries

    def test_con_compras_en_cuotas_inicio_se_ve_entero(self):
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000000'),
                                   categoria='Sueldo', fecha=date.today(), descripcion='Sueldo')
        self._compras(3)
        respuesta, _ = self._medir()
        self.assertContains(respuesta, 'Te queda $')
        self.assertContains(respuesta, 'id="modalCalendario"')
        self.assertContains(respuesta, 'id="modalMovimientos"')

    def test_lo_que_no_se_muestra_ya_no_se_calcula(self):
        self._compras(1)
        respuesta, _ = self._medir()
        for clave in ('mis_cuotas', 'fijo_mensual', 'cat_data_json', 'mapa_categorias', 'variacion_saldo',
                      'deuda_total', 'proximo_pago', 'hoy_texto'):
            self.assertNotIn(clave, respuesta.context, clave)

    @unittest.skipUnless(MEDIR, 'Medir las consultas de Inicio: MEDIR_INICIO=1')
    def test_medir(self):
        self._compras(2)
        _, pocas = self._medir()
        self._compras(10)
        _, muchas = self._medir()
        antes, despues = tablas(pocas), tablas(muchas)
        crecen = {t: f'{antes[t]} → {c}' for t, c in despues.most_common() if c > antes[t]}
        sys.stdout.write(f'\nInicio con 2 compras en cuotas: {len(pocas)} consultas. Con 12: {len(muchas)}.\n')
        sys.stdout.write(f'Tablas que crecen con las compras: {crecen or "ninguna"}\n')
        sys.stdout.write(f'Tablas más consultadas con 12: {dict(despues.most_common(8))}\n')
