import json
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from .. import fechas
from ..models import Deuda, MetaAhorro, Persona, Prestamo, Transaccion
from ..servicios.preguntas import HERRAMIENTAS, ejecutar, restaurar


class HerramientasTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = fechas.hoy()
        primero = self.hoy.replace(day=1)
        for atras in (1, 2, 3):
            f = (primero - relativedelta(months=atras)).replace(day=10)
            Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('1000000'),
                                       categoria='Sueldo', fecha=f)
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('400000'),
                                       categoria='Comida', fecha=f, pagado=True)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('35000'),
                                   categoria='Comida', fecha=self.hoy, pagado=True)
        Deuda.objects.create(usuario=self.ana, acreedor='Notebook Lenovo', monto_total=Decimal('120000'),
                             cuotas_totales=12, fecha_inicio=primero.replace(day=5))
        tia = Persona.objects.create(usuario=self.ana, nombre='Tía Rosa', lado='LE_DEBO')
        Prestamo.objects.create(persona=tia, descripcion='Arriendo', monto=Decimal('300000'),
                                tipo='CUOTAS', cuotas_totales=3, fecha=primero)
        MetaAhorro.objects.create(usuario=self.ana, nombre='Viaje a Chiloé', monto_meta=Decimal('500000'),
                                  monto_actual=Decimal('125000'), fecha_limite=self.hoy + timedelta(days=90))
        self.alias = {}

    def _usar(self, herramienta, **argumentos):
        return ejecutar(self.ana, herramienta, argumentos, self.alias)

    def test_hay_cinco_herramientas_con_esquema(self):
        self.assertEqual({h['name'] for h in HERRAMIENTAS},
                         {'simular_compra', 'queda_mes', 'gasto_categoria', 'fin_deuda', 'metas'})
        for h in HERRAMIENTAS:
            self.assertEqual(h['input_schema']['type'], 'object')

    def test_simular_compra(self):
        r = self._usar('simular_compra', monto=60000, cuotas=3)
        self.assertEqual(r['cuota'], 20000)
        self.assertEqual(r['cuotas'], 3)
        self.assertIn(r['mes_mas_justo'], [m['mes'] for m in r['meses']])
        self.assertIsInstance(r['alcanza'], bool)
        json.dumps(r)

    def test_simular_compra_rechaza_montos_raros(self):
        self.assertIn('error', self._usar('simular_compra', monto=-5))
        self.assertIn('error', self._usar('simular_compra', monto=1000, cuotas=40))
        self.assertIn('error', self._usar('simular_compra', monto='mucho'))

    def test_queda_mes(self):
        r = self._usar('queda_mes')
        self.assertEqual(set(r), {'mes', 'puedes_gastar', 'entro', 'gastado', 'falta_pagar',
                                  'dias_restantes', 'por_dia'})
        json.dumps(r)

    def test_gasto_categoria_sin_tildes_ni_mayusculas(self):
        r = self._usar('gasto_categoria', categoria='COMIDA')
        self.assertTrue(r['encontrada'])
        self.assertEqual(r['total'], 35000)
        self.assertEqual(r['total_mes_anterior'], 400000)

    def test_gasto_categoria_que_no_existe_ofrece_las_que_hay(self):
        r = self._usar('gasto_categoria', categoria='astronautas')
        self.assertFalse(r['encontrada'])
        self.assertTrue(r['categorias'])

    def test_fin_deuda_no_manda_nombres_reales(self):
        r = self._usar('fin_deuda')
        texto = json.dumps(r, ensure_ascii=False)
        self.assertNotIn('Notebook', texto)
        self.assertNotIn('Rosa', texto)
        self.assertEqual(len(r['deudas']), 2)
        notebook = next(d for d in r['deudas'] if d['tipo'] == 'compra en cuotas')
        self.assertEqual(notebook['cuotas_que_faltan'], 12)
        self.assertEqual(restaurar(f"{notebook['nombre']} termina en {notebook['termina']}", self.alias)[:15],
                         'Notebook Lenovo')

    def test_fin_deuda_filtra_por_nombre(self):
        r = self._usar('fin_deuda', nombre='notebook')
        self.assertEqual(len(r['deudas']), 1)

    def test_metas_con_alias(self):
        r = self._usar('metas')
        self.assertEqual(r['metas'][0]['porcentaje'], 25)
        self.assertEqual(r['metas'][0]['falta'], 375000)
        self.assertNotIn('Chiloé', json.dumps(r, ensure_ascii=False))
        self.assertEqual(restaurar(r['metas'][0]['nombre'], self.alias), 'Viaje a Chiloé')

    def test_herramienta_desconocida_y_argumentos_de_mas(self):
        self.assertIn('error', self._usar('borrar_todo'))
        self.assertNotIn('error', self._usar('queda_mes', usuario_id=99))

    def test_restaurar_no_confunde_alias_largos(self):
        alias = {f'Deuda {i}': f'Real {i}' for i in range(1, 12)}
        self.assertEqual(restaurar('Deuda 11 y Deuda 1', alias), 'Real 11 y Real 1')
