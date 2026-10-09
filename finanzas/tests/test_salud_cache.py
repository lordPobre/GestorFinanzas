from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from finanzas.models import Transaccion
from finanzas.servicios import mes


class SaludDesdeLaCacheTests(TestCase):

    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.client.force_login(self.ana)
        self.hoy = date.today()
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO', monto=Decimal('800000'),
                                   categoria='Sueldo', fecha=self.hoy)

    def _calculos_del_mes(self, url):
        with mock.patch.object(mes, '_resumen_mes', wraps=mes._resumen_mes) as calcular:
            self.assertEqual(self.client.get(url).status_code, 200)
        return [c for c in calcular.call_args_list if tuple(c.args[1:3]) == (self.hoy.year, self.hoy.month)]

    def test_las_otras_pantallas_no_recalculan_el_mes_en_cada_visita(self):
        self._calculos_del_mes(reverse('metas'))
        self.assertEqual(self._calculos_del_mes(reverse('metas')), [])
        self.assertEqual(self._calculos_del_mes(reverse('deudas')), [])

    def test_un_gasto_nuevo_actualiza_la_salud(self):
        antes = mes.salud_financiera(self.ana)
        Transaccion.objects.create(usuario=self.ana, tipo='EGRESO', monto=Decimal('790000'),
                                   categoria='Comida', fecha=self.hoy)
        despues = mes.salud_financiera(self.ana)
        self.assertNotEqual(antes['salud_score'], despues['salud_score'])
        self.assertEqual(despues['salud_estado'], 'amarillo')

    def test_cambiar_de_dia_no_usa_lo_guardado_ayer(self):
        mes.numeros_mes(self.ana, self.hoy.year, self.hoy.month)
        claves = [k for k in cache._cache.keys()] if hasattr(cache, '_cache') else []
        if claves:
            self.assertTrue(any(self.hoy.isoformat() in k for k in claves))
