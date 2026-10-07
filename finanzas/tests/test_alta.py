import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from finanzas import alta, legal, marketing
from finanzas.models import AltaPendiente, UserProfile


class Base(TestCase):

    def setUp(self):
        cache.clear()

    def _datos(self, **extra):
        datos = {
            'username': 'nueva', 'email_perfil': 'nueva@ejemplo.cl',
            'password1': 'contrasena-larga-77', 'password2': 'contrasena-larga-77',
            'nombre_completo': 'Persona Nueva', 'acepta_politica': '1',
        }
        datos.update(extra)
        return datos

    def _registrar(self, **extra):
        with mock.patch('finanzas.correo.enviar', return_value=True) as enviar:
            respuesta = self.client.post(reverse('registro'), self._datos(**extra))
        return respuesta, enviar

    def _token(self, enviar):
        return re.search(r'/registro/crear/([^/\s]+)/', enviar.call_args[0][2]).group(1)

    def _url(self, token):
        return reverse('confirmar_alta', args=[token])


class RegistroSinCuentaTodaviaTests(Base):

    def test_registrarse_no_crea_la_cuenta_y_manda_el_enlace(self):
        respuesta, enviar = self._registrar()
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username='nueva').exists())
        pendiente = AltaPendiente.objects.get(correo='nueva@ejemplo.cl')
        self.assertEqual((pendiente.username, pendiente.politica_version), ('nueva', legal.VERSION))
        self.assertEqual(enviar.call_args[0][0], 'nueva@ejemplo.cl')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_la_clave_y_el_enlace_no_quedan_en_claro(self):
        _, enviar = self._registrar()
        pendiente = AltaPendiente.objects.get()
        token = self._token(enviar)
        self.assertNotEqual(pendiente.token, token)
        self.assertNotIn('contrasena-larga-77', pendiente.password)
        self.assertTrue(User(password=pendiente.password).check_password('contrasena-larga-77'))

    def test_un_correo_con_cuenta_recibe_la_misma_respuesta(self):
        User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        nuevo, _ = self._registrar()
        self.client.get(reverse('login'))
        repetido, enviar = self._registrar(username='otra', email_perfil='ana@ejemplo.cl')
        self.assertEqual((nuevo.status_code, nuevo['Location']), (repetido.status_code, repetido['Location']))
        self.assertEqual(enviar.call_args[0][0], 'ana@ejemplo.cl')
        self.assertFalse(AltaPendiente.objects.filter(correo='ana@ejemplo.cl').exists())
        mensajes = [str(m) for m in self.client.get(reverse('login')).context['messages']]
        self.assertEqual(mensajes, ['Te mandamos un correo a ana@ejemplo.cl. Ábrelo para seguir.'])

    def test_volver_a_registrarse_reemplaza_el_enlace_anterior(self):
        _, primero = self._registrar()
        _, segundo = self._registrar()
        self.assertEqual(AltaPendiente.objects.count(), 1)
        self.assertContains(self.client.get(self._url(self._token(primero))), 'Este enlace ya no sirve')
        self.assertContains(self.client.get(self._url(self._token(segundo))), 'Crear mi cuenta')


class ConfirmarElAltaTests(Base):

    def setUp(self):
        super().setUp()
        _, enviar = self._registrar()
        self.token = self._token(enviar)

    def test_abrir_el_enlace_no_crea_nada(self):
        respuesta = self.client.get(self._url(self.token))
        self.assertContains(respuesta, 'Crear mi cuenta')
        self.assertFalse(User.objects.filter(username='nueva').exists())

    def test_confirmar_crea_la_cuenta_con_el_correo_verificado(self):
        respuesta = self.client.post(self._url(self.token))
        self.assertRedirects(respuesta, reverse('onboarding'), fetch_redirect_response=False)
        usuario = User.objects.get(username='nueva')
        self.assertEqual(usuario.email, 'nueva@ejemplo.cl')
        self.assertTrue(usuario.check_password('contrasena-larga-77'))
        perfil = UserProfile.objects.get(usuario=usuario)
        self.assertTrue(perfil.correo_verificado)
        self.assertEqual((perfil.politica_version, perfil.nombre_completo), (legal.VERSION, 'Persona Nueva'))
        self.assertIsNotNone(perfil.politica_aceptada)
        self.assertEqual(int(self.client.session['_auth_user_id']), usuario.pk)
        self.assertTrue(self.client.session.get(marketing.CLAVE_EVENTO))
        self.assertFalse(AltaPendiente.objects.exists())

    def test_el_enlace_sirve_una_sola_vez(self):
        self.client.post(self._url(self.token))
        self.client.logout()
        self.assertContains(self.client.post(self._url(self.token)), 'Este enlace ya no sirve')
        self.assertEqual(User.objects.filter(username='nueva').count(), 1)

    def test_un_enlace_vencido_no_sirve_y_se_borra(self):
        AltaPendiente.objects.update(creada=timezone.now() - timedelta(hours=alta.HORAS_VALIDEZ + 1))
        self.assertContains(self.client.post(self._url(self.token)), 'Este enlace ya no sirve')
        self.assertFalse(User.objects.filter(username='nueva').exists())
        self.assertFalse(AltaPendiente.objects.exists())

    def test_un_enlace_inventado_no_sirve(self):
        self.assertContains(self.client.post(self._url('inventado')), 'Este enlace ya no sirve')
        self.assertFalse(User.objects.filter(username='nueva').exists())

    def test_si_el_correo_ya_tiene_cuenta_no_duplica(self):
        User.objects.create_user('otra', 'nueva@ejemplo.cl', 'clave-larga-2')
        respuesta = self.client.post(self._url(self.token))
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username='nueva').exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_si_el_usuario_ya_lo_tomo_otra_persona_pide_otro(self):
        User.objects.create_user('Nueva', 'otra@ejemplo.cl', 'clave-larga-2')
        respuesta = self.client.post(self._url(self.token))
        self.assertRedirects(respuesta, reverse('registro'), fetch_redirect_response=False)
        self.assertEqual(User.objects.filter(username__iexact='nueva').count(), 1)

    def test_purgar_borra_solo_lo_vencido(self):
        AltaPendiente.objects.create(correo='vieja@ejemplo.cl', username='vieja', password='x',
                                     politica_version=legal.VERSION, token='a' * 64,
                                     creada=timezone.now() - timedelta(hours=alta.HORAS_VALIDEZ + 1))
        self.assertEqual(alta.purgar(), 1)
        self.assertEqual(AltaPendiente.objects.count(), 1)
