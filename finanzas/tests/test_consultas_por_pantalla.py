from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import Deuda, Persona, Prestamo, Suscripcion, Transaccion

TOPES = {
    'dashboard': 90,
    'estadisticas': 60,
    'perfil': 35,
    'categorias': 32,
    'suscripciones': 30,
    'prestamos': 28,
    'deudas': 27,
    'metas': 26,
}
PANTALLAS = tuple(TOPES)


class ConsultasPorPantallaTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        hoy = date.today()
        for i in range(12):
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(1000 + i),
                                       categoria='Comida', fecha=hoy.replace(day=1), descripcion=f'Gasto {i}')
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('900000'),
                                   categoria='Sueldo', fecha=hoy.replace(day=1))
        for i in range(3):
            Deuda.objects.create(usuario=self.ana, acreedor=f'Tienda {i}', monto_total=Decimal('60000'),
                                 cuotas_totales=6, fecha_inicio=hoy.replace(day=1))
            Suscripcion.objects.create(usuario=self.ana, nombre=f'Servicio {i}', monto=Decimal('5990'),
                                       dia_cobro=5, fecha_inicio=hoy.replace(day=1))
        camila = Persona.objects.create(usuario=self.ana, nombre='Camila', lado='ME_DEBE')
        Prestamo.objects.create(persona=camila, descripcion='Arriendo', monto=Decimal('180000'),
                                tipo='UNICO', cuotas_totales=1)

    def _contar(self, nombre):
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse(nombre))
        self.assertEqual(respuesta.status_code, 200, nombre)
        return len(consultas.captured_queries)

    def test_ninguna_pantalla_pasa_el_tope(self):
        for nombre in PANTALLAS:
            self._contar(nombre)
        medidas = {nombre: self._contar(nombre) for nombre in PANTALLAS}
        pasadas = {n: f'{c} de {TOPES[n]}' for n, c in medidas.items() if c > TOPES[n]}
        self.assertFalse(pasadas, f'Consultas por pantalla: {medidas}')

    def test_la_segunda_visita_no_cuesta_mas_que_la_primera(self):
        for nombre in ('metas', 'deudas', 'prestamos'):
            primera = self._contar(nombre)
            segunda = self._contar(nombre)
            self.assertLessEqual(segunda, primera, nombre)

    def test_mas_movimientos_no_suman_consultas(self):
        antes = self._contar('metas')
        hoy = date.today()
        for i in range(20):
            Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal(500 + i),
                                       categoria='Ocio', fecha=hoy.replace(day=1))
        self._contar('metas')
        despues = self._contar('metas')
        self.assertLessEqual(despues, antes + 2)
