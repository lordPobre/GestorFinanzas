from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from finanzas import rendimiento
from finanzas.models import Transaccion
from finanzas.servicios import mes


class LoCalculadoEnLaPeticionTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.hoy = date.today()

    def _ingreso(self, monto):
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal(monto),
                                   categoria='Sueldo', fecha=self.hoy, descripcion='Sueldo')

    def test_el_inicio_calcula_el_mes_una_sola_vez(self):
        self.client.force_login(self.ana)
        with mock.patch.object(mes, '_resumen_mes', wraps=mes._resumen_mes) as calcular:
            self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        del_mes = [c for c in calcular.call_args_list
                   if tuple(c.args[1:3]) == (self.hoy.year, self.hoy.month)]
        self.assertEqual(len(del_mes), 1)

    def test_fuera_de_una_peticion_no_recuerda(self):
        with mock.patch.object(mes, '_resumen_mes', wraps=mes._resumen_mes) as calcular:
            mes.resumen_mes(self.ana, self.hoy.year, self.hoy.month)
            mes.resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        self.assertEqual(calcular.call_count, 2)

    def test_un_cambio_en_los_datos_borra_lo_recordado(self):
        token = rendimiento._memo.set({})
        try:
            antes = mes.resumen_mes(self.ana, self.hoy.year, self.hoy.month)['ingresos']
            self._ingreso('500000')
            despues = mes.resumen_mes(self.ana, self.hoy.year, self.hoy.month)['ingresos']
        finally:
            rendimiento._memo.reset(token)
        self.assertEqual((antes, despues), (0.0, 500000.0))

    def test_cada_llamada_recibe_su_propia_copia(self):
        token = rendimiento._memo.set({})
        try:
            primero = mes.resumen_mes(self.ana, self.hoy.year, self.hoy.month)
            primero['ingresos'] = 999
            segundo = mes.resumen_mes(self.ana, self.hoy.year, self.hoy.month)
        finally:
            rendimiento._memo.reset(token)
        self.assertEqual(segundo['ingresos'], 0.0)


class MedicionTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    @override_settings(RESPUESTA_LENTA_MS=0)
    def test_una_respuesta_lenta_queda_en_el_registro(self):
        self.client.force_login(self.ana)
        with self.assertLogs('finanzas', 'WARNING') as registro:
            self.client.get(reverse('dashboard'))
        self.assertTrue(any('Respuesta lenta: GET' in linea for linea in registro.output))

    def test_los_tiempos_solo_los_ve_el_personal(self):
        self.client.force_login(self.ana)
        self.assertNotIn('Server-Timing', self.client.get(reverse('dashboard')).headers)
        self.ana.is_staff = True
        self.ana.save(update_fields=['is_staff'])
        tiempos = self.client.get(reverse('dashboard')).headers['Server-Timing']
        self.assertIn('app;dur=', tiempos)
        self.assertIn('consultas', tiempos)
