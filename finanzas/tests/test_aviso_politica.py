from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from finanzas import correo, legal
from finanzas.models import UserProfile


class AvisoDeLaPoliticaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')

    def _correr(self, *args, sale=True):
        salida = StringIO()
        with mock.patch.object(correo, 'enviar', return_value=sale) as enviar:
            call_command('avisar_politica', *args, '--pausa', '0', stdout=salida)
        return enviar, salida.getvalue()

    def _avisada(self, usuario):
        return UserProfile.objects.get(usuario=usuario).politica_avisada

    def test_avisa_a_cada_cuenta_una_sola_vez(self):
        enviar, salida = self._correr()
        self.assertEqual({c[0][0] for c in enviar.call_args_list}, {'ana@ejemplo.cl', 'beto@ejemplo.cl'})
        self.assertIn('2 enviados', salida)
        self.assertEqual(self._avisada(self.ana), legal.VERSION)
        enviar, _ = self._correr()
        enviar.assert_not_called()

    def test_el_correo_trae_la_version_los_cambios_y_los_enlaces(self):
        enviar, _ = self._correr('--usuario', 'ana')
        destino, asunto, texto, html = enviar.call_args[0]
        self.assertEqual(destino, 'ana@ejemplo.cl')
        self.assertIn('política de privacidad', asunto)
        for cuerpo in (texto, html):
            self.assertIn(legal.VERSION, cuerpo)
            self.assertIn(legal.VIGENTE_DESDE, cuerpo)
            self.assertIn('/privacidad/', cuerpo)
            self.assertIn(legal.CORREO_CONTACTO, cuerpo)
            for titulo, _ in legal.CAMBIOS:
                self.assertIn(titulo, cuerpo)
        self.assertIn('cid:fintora-cabecera', html)

    def test_en_seco_no_envia_ni_marca(self):
        enviar, salida = self._correr('--seco')
        enviar.assert_not_called()
        self.assertIn('2 cuentas por avisar', salida)
        self.assertEqual(self._avisada(self.ana), '')

    def test_si_el_correo_no_sale_la_cuenta_queda_pendiente(self):
        with self.assertLogs('finanzas', 'WARNING'):
            _, salida = self._correr(sale=False)
        self.assertIn('2 no salieron', salida)
        self.assertEqual(self._avisada(self.ana), '')

    def test_sin_correo_o_inactiva_no_se_avisa(self):
        User.objects.create_user('carla', '', 'clave-larga-3')
        User.objects.create_user('dani', 'dani@ejemplo.cl', 'clave-larga-4', is_active=False)
        enviar, salida = self._correr()
        self.assertEqual(enviar.call_count, 2)
        self.assertIn('1 sin correo', salida)

    def test_usa_el_correo_del_perfil_si_la_cuenta_no_tiene(self):
        carla = User.objects.create_user('carla', '', 'clave-larga-3')
        perfil, _ = UserProfile.objects.get_or_create(usuario=carla)
        perfil.email = 'carla@ejemplo.cl'
        perfil.save(update_fields=['email'])
        enviar, _ = self._correr('--usuario', 'carla')
        self.assertEqual(enviar.call_args[0][0], 'carla@ejemplo.cl')

    def test_una_version_nueva_se_vuelve_a_avisar(self):
        self._correr()
        with mock.patch.object(legal, 'VERSION', '9.9'):
            enviar, _ = self._correr()
        self.assertEqual(enviar.call_count, 2)
        self.assertEqual(self._avisada(self.ana), '9.9')

    def test_el_limite_corta_la_tanda(self):
        enviar, _ = self._correr('--limite', '1')
        self.assertEqual(enviar.call_count, 1)
        enviar, _ = self._correr()
        self.assertEqual(enviar.call_count, 1)
