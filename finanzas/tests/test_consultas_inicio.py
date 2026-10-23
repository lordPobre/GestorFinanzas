import os
import re
import sys
import traceback
import unittest
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import Deuda, PagoCuota, Transaccion

MEDIR = os.environ.get('MEDIR_INICIO') == '1'
TABLA = re.compile(r'FROM "(\w+)"')
RAIZ = str(Path(settings.BASE_DIR).resolve())
TOPE_INICIO = 54


def tablas(consultas):
    return Counter(t for q in consultas for t in TABLA.findall(q['sql']))


def origen():
    for marco in reversed(traceback.extract_stack()[:-3]):
        ruta = str(Path(marco.filename).resolve())
        if ruta.startswith(RAIZ) and 'site-packages' not in ruta and os.sep + 'tests' + os.sep not in ruta:
            return f'{os.path.relpath(ruta, RAIZ)}:{marco.lineno} {marco.name}'
    return 'django'


class Anotador:

    def __init__(self):
        self.por_origen = Counter()
        self.ejemplo = {}
        self.tablas = defaultdict(Counter)

    def __call__(self, ejecutar, sql, params, many, contexto):
        donde = origen()
        self.por_origen[donde] += 1
        self.ejemplo.setdefault(donde, ' '.join(sql.split())[:110])
        for t in TABLA.findall(sql):
            self.tablas[donde][t] += 1
        return ejecutar(sql, params, many, contexto)


CACHE_COMO_PRODUCCION = {'default': {'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
                                     'LOCATION': 'cache_finapp'}}


@override_settings(CACHES=CACHE_COMO_PRODUCCION)
class ConsultasInicioTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command('createcachetable', verbosity=0)

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

    def _anotar(self):
        cache.clear()
        anotador = Anotador()
        with connection.execute_wrapper(anotador):
            respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        return anotador

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
                      'deuda_total', 'proximo_pago', 'hoy_texto', 'calendario', 'dias_con_pago',
                      'monto_ya_pagado', 'gastos_pendientes', 'dias_semana', 'movimientos_mes',
                      'mov_entro', 'mov_salio', 'mov_n_unicos'):
            self.assertNotIn(clave, respuesta.context, clave)

    def test_inicio_no_pasa_el_tope_y_no_crece_con_las_compras(self):
        self._compras(2)
        _, pocas = self._medir()
        self._compras(10)
        _, muchas = self._medir()
        self.assertLessEqual(len(muchas), len(pocas) + 2)
        self.assertLessEqual(len(muchas), TOPE_INICIO, f'Inicio hizo {len(muchas)} consultas')

    @unittest.skipUnless(MEDIR, 'Medir las consultas de Inicio: MEDIR_INICIO=1')
    def test_medir(self):
        self._compras(2)
        _, pocas = self._medir()
        self._compras(10)
        _, muchas = self._medir()
        antes, despues = tablas(pocas), tablas(muchas)
        crecen = {t: f'{antes[t]} → {c}' for t, c in despues.most_common() if c > antes[t]}
        salida = [
            f'\nInicio con 2 compras en cuotas: {len(pocas)} consultas. Con 12: {len(muchas)}.',
            f'Tablas que crecen con las compras: {crecen or "ninguna"}',
            f'Tablas más consultadas con 12: {dict(despues.most_common(8))}',
            '',
            'Consultas por línea de código (con 12 compras):',
        ]
        anotador = self._anotar()
        for donde, n in anotador.por_origen.most_common():
            tablas_linea = ', '.join(f'{t}×{c}' for t, c in anotador.tablas[donde].most_common())
            salida.append(f'{n:>3}  {donde}  [{tablas_linea}]')
            salida.append(f'     {anotador.ejemplo[donde]}')
        sys.stdout.write('\n'.join(salida) + '\n')
