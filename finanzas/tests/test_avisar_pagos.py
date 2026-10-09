from datetime import date
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from finanzas import correo
from finanzas.models import GastoPendiente, UserProfile


def _dia_fijo(fecha):
    class Fijo(date):
        @classmethod
        def today(cls):
            return cls(fecha.year, fecha.month, fecha.day)
    return Fijo


class AvisarPagosTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)
        self.perfil.aviso_dia = 31
        self.perfil.save(update_fields=['aviso_dia'])

    def _pendiente(self, fecha):
        GastoPendiente.objects.create(usuario=self.ana, nombre='Luz', monto=Decimal('30000'),
                                      fecha_vencimiento=fecha)

    def _correr(self, hoy, *args, sale=True):
        fijo = _dia_fijo(hoy)
        salida = StringIO()
        with mock.patch('finanzas.management.commands.avisar_pagos.date', fijo), \
                mock.patch('finanzas.models.perfil.date', fijo), \
                mock.patch.object(correo, 'enviar', return_value=sale) as enviar:
            call_command('avisar_pagos', *args, stdout=salida)
        return enviar, salida.getvalue()

    def _periodo(self):
        return UserProfile.objects.get(usuario=self.ana).aviso_ultimo_periodo

    def test_en_febrero_un_aviso_del_31_sale_el_28(self):
        self._pendiente(date(2027, 2, 10))
        enviar, _ = self._correr(date(2027, 2, 28))
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args[0][0], 'ana@ejemplo.cl')
        self.assertEqual(self._periodo(), 202702)

    def test_el_27_de_febrero_todavia_no_sale(self):
        self._pendiente(date(2027, 2, 10))
        enviar, _ = self._correr(date(2027, 2, 27))
        enviar.assert_not_called()
        self.assertEqual(self._periodo(), 0)

    def test_en_un_mes_de_30_dias_sale_el_30(self):
        self._pendiente(date(2027, 4, 10))
        enviar, _ = self._correr(date(2027, 4, 30))
        enviar.assert_called_once()

    def test_sale_una_sola_vez_por_periodo(self):
        self._pendiente(date(2027, 2, 10))
        self._correr(date(2027, 2, 28))
        enviar, _ = self._correr(date(2027, 2, 28))
        enviar.assert_not_called()

    def test_al_mes_siguiente_vuelve_a_salir(self):
        self._pendiente(date(2027, 2, 10))
        self._correr(date(2027, 2, 28))
        enviar, _ = self._correr(date(2027, 3, 31))
        enviar.assert_called_once()
        self.assertEqual(self._periodo(), 202703)

    def test_si_el_correo_no_sale_se_reintenta(self):
        self._pendiente(date(2027, 2, 10))
        _, salida = self._correr(date(2027, 2, 28), sale=False)
        self.assertIn('1 con error', salida)
        self.assertEqual(self._periodo(), 0)
        enviar, _ = self._correr(date(2027, 2, 28))
        enviar.assert_called_once()
        self.assertEqual(self._periodo(), 202702)

    def test_forzar_ignora_el_dia_y_el_registro(self):
        self._pendiente(date(2027, 2, 10))
        enviar, _ = self._correr(date(2027, 2, 10), '--forzar')
        enviar.assert_called_once()

    def test_en_seco_no_envia_ni_marca(self):
        self._pendiente(date(2027, 2, 10))
        enviar, salida = self._correr(date(2027, 2, 28), '--seco')
        enviar.assert_not_called()
        self.assertIn('ana@ejemplo.cl', salida)
        self.assertEqual(self._periodo(), 0)

    def test_sin_nada_por_pagar_no_envia(self):
        enviar, salida = self._correr(date(2027, 2, 28))
        enviar.assert_not_called()
        self.assertIn('nada por pagar', salida)

    def test_con_el_aviso_apagado_no_envia(self):
        self._pendiente(date(2027, 2, 10))
        self.perfil.aviso_mensual = False
        self.perfil.save(update_fields=['aviso_mensual'])
        enviar, _ = self._correr(date(2027, 2, 28))
        enviar.assert_not_called()
