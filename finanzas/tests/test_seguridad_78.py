import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import signing
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..aparatos import COOKIE
from ..models import Contador, EventoSeguridad, SegundoFactor, UserProfile
from ..seguridad import MAX_INTENTOS, esta_bloqueado, red, registrar_fallo, sumar
from ..views.cuenta import SAL_CAMBIO_CORREO

CLAVE = 'clave-larga-123'


class RedTests(SimpleTestCase):

    def test_ipv6_se_agrupa_por_64(self):
        self.assertEqual(red('2001:db8:1:2:aaaa::1'), red('2001:db8:1:2:ffff::9'))
        self.assertNotEqual(red('2001:db8:1:2::1'), red('2001:db8:1:3::1'))

    def test_ipv4_queda_igual(self):
        self.assertEqual(red('10.0.0.1'), '10.0.0.1')
        self.assertEqual(red('::ffff:10.0.0.1'), '10.0.0.1')

    def test_valor_raro_no_rompe(self):
        self.assertEqual(red('desconocida'), 'desconocida')


class ContadorTests(TestCase):

    def test_suma_y_reinicia_al_vencer(self):
        self.assertEqual(sumar('x', 60)[0], 1)
        self.assertEqual(sumar('x', 60)[0], 2)
        Contador.objects.filter(clave='x').update(vence=timezone.now() - timedelta(seconds=1))
        self.assertEqual(sumar('x', 60)[0], 1)

    def test_misma_red_ipv6_comparte_bloqueo(self):
        for _ in range(MAX_INTENTOS):
            registrar_fallo('ana', '2001:db8:1:2::1')
        self.assertGreater(esta_bloqueado('ana', '2001:db8:1:2::99'), 0)
        self.assertEqual(esta_bloqueado('ana', '2001:db8:9:9::1'), 0)


class ContrasenaEnSesionTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', CLAVE)
        self.client.force_login(self.ana)

    def test_cambiar_contrasena_tiene_tope(self):
        malo = {'accion': 'password', 'old_password': 'no-es', 'new_password1': 'Otra-clave-987',
                'new_password2': 'Otra-clave-987'}
        for _ in range(MAX_INTENTOS):
            self.client.post(reverse('perfil'), malo)
        bueno = dict(malo, old_password=CLAVE)
        respuesta = self.client.post(reverse('perfil'), bueno, follow=True)
        self.assertContains(respuesta, 'Demasiados intentos')
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password(CLAVE))


class CambioCorreoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', CLAVE)
        UserProfile.objects.update_or_create(
            usuario=self.ana, defaults={'email': 'ana@ejemplo.cl', 'correo_verificado': True})
        self.client.force_login(self.ana)

    def _pedir(self, **extra):
        datos = {'accion': 'perfil', 'nombre_completo': 'Ana', 'email': 'nueva@ejemplo.cl',
                 'moneda': 'CLP', **extra}
        return self.client.post(reverse('perfil'), datos)

    def test_sin_contrasena_no_cambia(self):
        self._pedir()
        perfil = UserProfile.objects.get(usuario=self.ana)
        self.assertEqual(perfil.email_pendiente, '')
        self.assertEqual(User.objects.get(pk=self.ana.pk).email, 'ana@ejemplo.cl')

    def test_con_contrasena_queda_pendiente(self):
        self._pedir(password_actual=CLAVE)
        perfil = UserProfile.objects.get(usuario=self.ana)
        self.assertEqual(perfil.email_pendiente, 'nueva@ejemplo.cl')
        self.assertEqual(perfil.email, 'ana@ejemplo.cl')
        self.assertEqual(User.objects.get(pk=self.ana.pk).email, 'ana@ejemplo.cl')
        self.assertTrue(EventoSeguridad.objects.filter(tipo='correo_cambio_pedido').exists())

    def test_el_enlace_cambia_el_correo_y_cierra_las_otras_sesiones(self):
        otro = Client()
        otro.force_login(self.ana)
        self._pedir(password_actual=CLAVE)
        token = signing.dumps({'uid': self.ana.pk, 'nuevo': 'nueva@ejemplo.cl',
                               'actual': 'ana@ejemplo.cl'}, salt=SAL_CAMBIO_CORREO)
        self.client.get(reverse('confirmar_cambio_correo', args=[token]))
        self.assertEqual(User.objects.get(pk=self.ana.pk).email, 'nueva@ejemplo.cl')
        perfil = UserProfile.objects.get(usuario=self.ana)
        self.assertEqual(perfil.email_pendiente, '')
        self.assertEqual(self.client.get(reverse('perfil')).status_code, 200)
        self.assertEqual(otro.get(reverse('perfil')).status_code, 302)

    def test_enlace_viejo_no_sirve_tras_otro_pedido(self):
        self._pedir(password_actual=CLAVE)
        token = signing.dumps({'uid': self.ana.pk, 'nuevo': 'nueva@ejemplo.cl',
                               'actual': 'ana@ejemplo.cl'}, salt=SAL_CAMBIO_CORREO)
        self._pedir(password_actual=CLAVE, email='otra@ejemplo.cl')
        self.client.get(reverse('confirmar_cambio_correo', args=[token]))
        self.assertEqual(User.objects.get(pk=self.ana.pk).email, 'ana@ejemplo.cl')


class VencimientosTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', CLAVE)

    def test_codigo_de_dos_pasos_vence(self):
        SegundoFactor.objects.create(usuario=self.ana, secreto='A' * 16, activo=True)
        sesion = self.client.session
        sesion['2fa_pendiente'] = self.ana.pk
        sesion['2fa_desde'] = time.time() - 600
        sesion.save()
        respuesta = self.client.get(reverse('verificar_codigo'))
        self.assertEqual(respuesta['Location'], reverse('login'))
        self.assertNotIn('2fa_pendiente', self.client.session)

    @override_settings(SESION_MAXIMA_HORAS=1)
    def test_sesion_vence_aunque_se_use(self):
        self.client.force_login(self.ana)
        sesion = self.client.session
        sesion['inicio_sesion'] = time.time() - 7200
        sesion.save()
        respuesta = self.client.get(reverse('perfil'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(EventoSeguridad.objects.filter(tipo='sesion_vencida').exists())


class AparatoConocidoTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', CLAVE)

    def _entrar(self, cliente):
        return cliente.post(reverse('login'), {'username': 'ana', 'password': CLAVE})

    def test_primer_aparato_no_avisa_y_deja_cookie(self):
        respuesta = self._entrar(self.client)
        self.assertIn(COOKIE, respuesta.cookies)
        self.assertFalse(EventoSeguridad.objects.filter(tipo='dispositivo_nuevo').exists())

    def test_mismo_aparato_no_avisa(self):
        self._entrar(self.client)
        self.client.post(reverse('logout'))
        self._entrar(self.client)
        self.assertFalse(EventoSeguridad.objects.filter(tipo='dispositivo_nuevo').exists())

    def test_aparato_nuevo_queda_anotado(self):
        self._entrar(self.client)
        self._entrar(Client())
        self.assertTrue(EventoSeguridad.objects.filter(tipo='dispositivo_nuevo').exists())
