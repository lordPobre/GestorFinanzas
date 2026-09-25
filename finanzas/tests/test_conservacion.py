from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .. import inactividad
from ..cartolas.base import (MAX_MOVIMIENTOS, MAX_PAGINAS, Cartola, ErrorCartola,
                            MovimientoLeido, _topar, texto_de_pdf)
from ..models import Transaccion, UserProfile


def _cuenta(nombre, dias_sin_entrar, **extra):
    ahora = timezone.now()
    viejo = ahora - timedelta(days=dias_sin_entrar)

    usuario = User.objects.create_user(nombre, f'{nombre}@ejemplo.cl', 'clave-larga-1',
                                       **extra)
    User.objects.filter(pk=usuario.pk).update(date_joined=viejo, last_login=None)
    usuario.refresh_from_db()

    perfil, _ = UserProfile.objects.get_or_create(usuario=usuario)
    perfil.ultima_actividad = viejo
    perfil.save(update_fields=['ultima_actividad'])
    return usuario, perfil


class SeleccionDeCuentas(TestCase):
    def test_una_cuenta_en_uso_no_entra_en_la_lista(self):
        _cuenta('activa', 5)
        self.assertEqual(inactividad.por_avisar(), [])

    def test_una_cuenta_abandonada_entra(self):
        _cuenta('vieja', 400)
        nombres = [u.username for u, _ in inactividad.por_avisar()]
        self.assertEqual(nombres, ['vieja'])

    def test_la_sesion_abierta_cuenta_como_actividad(self):
        usuario, perfil = _cuenta('fiel', 400)
        perfil.ultima_actividad = timezone.now() - timedelta(days=3)
        perfil.save(update_fields=['ultima_actividad'])

        self.assertEqual(inactividad.por_avisar(), [])

    def test_los_superusuarios_quedan_fuera(self):
        _cuenta('jefe', 400, is_superuser=True, is_staff=True)
        self.assertEqual(inactividad.por_avisar(), [])

    def test_avisada_una_vez_no_se_vuelve_a_avisar(self):
        usuario, perfil = _cuenta('vieja', 400)
        perfil.aviso_inactividad_enviado = timezone.now()
        perfil.save(update_fields=['aviso_inactividad_enviado'])

        self.assertEqual(inactividad.por_avisar(), [])


class ElAviso(TestCase):
    def setUp(self):
        self.usuario, self.perfil = _cuenta('vieja', 400)

    def test_si_el_correo_sale_queda_la_fecha(self):
        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            self.assertTrue(inactividad.avisar(self.usuario, self.perfil))

        self.assertEqual(enviar.call_args[0][0], 'vieja@ejemplo.cl')
        self.perfil.refresh_from_db()
        self.assertIsNotNone(self.perfil.aviso_inactividad_enviado)

    def test_si_el_correo_falla_la_cuenta_no_queda_avisada(self):
        with patch('finanzas.correo.enviar', return_value=False):
            self.assertFalse(inactividad.avisar(self.usuario, self.perfil))

        self.perfil.refresh_from_db()
        self.assertIsNone(self.perfil.aviso_inactividad_enviado)

    def test_sin_correo_no_se_avisa(self):
        User.objects.filter(pk=self.usuario.pk).update(email='')
        self.usuario.refresh_from_db()
        self.perfil.email = ''
        self.perfil.save(update_fields=['email'])

        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            self.assertFalse(inactividad.avisar(self.usuario, self.perfil))
        enviar.assert_not_called()


class ElBorrado(TestCase):
    def setUp(self):
        self.usuario, self.perfil = _cuenta('vieja', 400)
        Transaccion.objects.create(usuario=self.usuario, tipo='EGRESO',
                                   monto=Decimal('1000'), categoria='Otros',
                                   fecha=timezone.localdate())

    def _avisada_hace(self, dias):
        self.perfil.aviso_inactividad_enviado = timezone.now() - timedelta(days=dias)
        self.perfil.save(update_fields=['aviso_inactividad_enviado'])

    def test_no_se_borra_sin_aviso(self):
        self.assertEqual(inactividad.por_borrar(), [])

    def test_no_se_borra_durante_el_plazo_de_gracia(self):
        self._avisada_hace(inactividad.DIAS_GRACIA - 2)
        self.assertEqual(inactividad.por_borrar(), [])

    def test_se_borra_pasado_el_plazo(self):
        self._avisada_hace(inactividad.DIAS_GRACIA + 1)
        nombres = [u.username for u, _ in inactividad.por_borrar()]
        self.assertEqual(nombres, ['vieja'])

    def test_quien_vuelve_sale_de_la_cola_y_se_le_limpia_la_marca(self):
        self._avisada_hace(inactividad.DIAS_GRACIA + 1)
        self.perfil.ultima_actividad = timezone.now() - timedelta(days=1)
        self.perfil.save(update_fields=['ultima_actividad'])

        self.assertEqual(inactividad.por_borrar(), [])
        self.perfil.refresh_from_db()
        self.assertIsNone(self.perfil.aviso_inactividad_enviado)

    def test_borrar_se_lleva_todo(self):
        uid = self.usuario.pk
        inactividad.borrar(self.usuario, self.perfil)

        self.assertFalse(User.objects.filter(pk=uid).exists())
        self.assertFalse(Transaccion.objects.filter(usuario_id=uid).exists())
        self.assertFalse(UserProfile.objects.filter(usuario_id=uid).exists())


class LaTareaCompleta(TestCase):
    def test_seco_no_envia_ni_borra(self):
        from django.core.management import call_command
        from io import StringIO

        usuario, perfil = _cuenta('vieja', 400)
        salida = StringIO()

        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            call_command('limpiar_inactivas', '--seco', stdout=salida)

        enviar.assert_not_called()
        perfil.refresh_from_db()
        self.assertIsNone(perfil.aviso_inactividad_enviado)
        self.assertIn('avisaría a vieja', salida.getvalue())

    def test_una_corrida_avisa_y_la_siguiente_no_repite(self):
        from django.core.management import call_command
        from io import StringIO

        usuario, perfil = _cuenta('vieja', 400)

        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            call_command('limpiar_inactivas', stdout=StringIO())
            self.assertEqual(enviar.call_count, 1)
            call_command('limpiar_inactivas', stdout=StringIO())
            self.assertEqual(enviar.call_count, 1)


class TopesDeCartola(TestCase):
    def _cartola(self, cuantos):
        hoy = timezone.localdate()
        movs = [MovimientoLeido(fecha=hoy, descripcion='x', monto=Decimal('1'),
                                tipo='EGRESO', saldo=Decimal('0'))
                for _ in range(cuantos)]
        return Cartola(banco='Prueba', movimientos=movs)

    def test_una_cartola_normal_pasa(self):
        c = self._cartola(120)
        self.assertIs(_topar(c), c)

    def test_demasiados_movimientos_se_rechazan_enteros(self):
        with self.assertRaises(ErrorCartola):
            _topar(self._cartola(MAX_MOVIMIENTOS + 1))

    def test_demasiadas_paginas_se_rechazan(self):
        class PaginaFalsa:
            def extract_text(self):
                return 'texto'

        class LectorFalso:
            is_encrypted = False

            def __init__(self, *a, **k):
                self.pages = [PaginaFalsa()] * (MAX_PAGINAS + 5)

        with patch('pypdf.PdfReader', LectorFalso):
            with self.assertRaises(ErrorCartola) as caja:
                texto_de_pdf(b'no importa')

        self.assertIn('páginas', str(caja.exception))

    def test_demasiado_texto_se_rechaza(self):
        class PaginaGorda:
            def extract_text(self):
                return 'a' * 200_000

        class LectorFalso:
            is_encrypted = False

            def __init__(self, *a, **k):
                self.pages = [PaginaGorda()] * 40

        with patch('pypdf.PdfReader', LectorFalso):
            with self.assertRaises(ErrorCartola):
                texto_de_pdf(b'no importa')
