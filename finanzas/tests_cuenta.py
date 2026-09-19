"""Tests del área de cuenta: confirmación del correo y sesiones abiertas.

El correo es lo único que permite recuperar una cuenta, así que lo que se
comprueba acá es que no se dé por bueno sin que nadie lo confirme: ni al
registrarse, ni al cambiarlo después, ni con un enlace viejo.

De las sesiones se comprueba lo único que importa de verdad: que cerrar una a
distancia deje al otro navegador fuera en la petición siguiente, y que la
clave de sesión de un tercero no sirva para cerrarle la suya.
"""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from . import verificacion
from .models import SesionActiva, UserProfile


class ConfirmacionAlRegistrarse(TestCase):
    URL = '/registro/'

    def setUp(self):
        cache.clear()

    def _datos(self, **extra):
        datos = {
            'username': 'nueva',
            'email_perfil': 'nueva@ejemplo.cl',
            'password1': 'contrasena-larga-77',
            'password2': 'contrasena-larga-77',
            'nombre_completo': 'Persona Nueva',
            'acepta_politica': '1',
        }
        datos.update(extra)
        return datos

    def test_el_alta_manda_el_correo_y_deja_sin_confirmar(self):
        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            self.client.post(self.URL, self._datos())

        usuario = User.objects.get(username='nueva')
        perfil = UserProfile.objects.get(usuario=usuario)
        self.assertFalse(perfil.correo_verificado)
        self.assertEqual(enviar.call_args[0][0], 'nueva@ejemplo.cl')

    def test_no_confirmar_no_impide_usar_la_app(self):
        """Exigirlo dejaría fuera a quien se registra donde no tiene su
        correo abierto."""
        with patch('finanzas.correo.enviar', return_value=True):
            self.client.post(self.URL, self._datos())

        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)


class ElEnlaceDeConfirmacion(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil = UserProfile.objects.create(usuario=self.ana)

    def _url(self, usuario=None):
        return reverse('verificar_correo',
                       kwargs={'token': verificacion.token(usuario or self.ana)})

    def test_abrirlo_confirma(self):
        respuesta = self.client.get(self._url())
        self.assertEqual(respuesta.status_code, 200)

        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.correo_verificado)
        self.assertIsNotNone(self.perfil.correo_verificado_en)

    def test_no_inicia_sesion(self):
        """Abrir el enlace prueba que la dirección existe, no que quien lo
        abre sea el dueño de la cuenta."""
        self.client.get(self._url())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_un_token_inventado_no_confirma(self):
        respuesta = self.client.get(
            reverse('verificar_correo', kwargs={'token': 'esto-no-va-firmado'}))
        self.assertEqual(respuesta.status_code, 200)

        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.correo_verificado)

    def test_cambiar_el_correo_invalida_el_enlace_anterior(self):
        url = self._url()
        self.ana.email = 'otra@ejemplo.cl'
        self.ana.save(update_fields=['email'])

        self.client.get(url)
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.correo_verificado)

    def test_cambiar_el_correo_en_el_perfil_lo_deja_sin_confirmar(self):
        verificacion.marcar(self.perfil)
        self.client.force_login(self.ana)

        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            self.client.post(reverse('perfil'), {
                'accion': 'perfil',
                'nombre_completo': 'Ana',
                'email': 'nueva-direccion@ejemplo.cl',
                'moneda': 'CLP',
            })

        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.correo_verificado)
        self.assertEqual(enviar.call_args[0][0], 'nueva-direccion@ejemplo.cl')

    def test_reenviar_no_hace_nada_si_ya_esta_confirmado(self):
        verificacion.marcar(self.perfil)
        self.client.force_login(self.ana)

        with patch('finanzas.correo.enviar', return_value=True) as enviar:
            self.client.post(reverse('reenviar_verificacion'))
        enviar.assert_not_called()


class SesionesAbiertas(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.create(usuario=self.ana)

    def test_entrar_deja_la_sesion_anotada(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})

        fila = SesionActiva.objects.filter(usuario=self.ana).first()
        self.assertIsNotNone(fila)
        self.assertEqual(fila.clave, self.client.session.session_key)

    def test_la_pantalla_marca_la_sesion_en_uso(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        cuerpo = self.client.get(reverse('sesiones_activas')).content.decode('utf-8')
        self.assertIn('Esta sesión', cuerpo)

    def test_cerrar_las_demas_deja_al_otro_navegador_fuera(self):
        from django.test import Client

        primero, segundo = Client(), Client()
        primero.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        segundo.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.assertEqual(SesionActiva.objects.filter(usuario=self.ana).count(), 2)

        primero.post(reverse('sesiones_activas'), {'accion': 'cerrar_todas'})

        self.assertEqual(SesionActiva.objects.filter(usuario=self.ana).count(), 1)
        # El segundo navegador ya no tiene sesión válida: la vista protegida
        # lo manda al acceso.
        respuesta = segundo.get(reverse('perfil'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

        # El primero sigue dentro.
        self.assertEqual(primero.get(reverse('perfil')).status_code, 200)

    def test_no_se_puede_cerrar_la_sesion_de_otra_persona(self):
        from django.test import Client

        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        UserProfile.objects.create(usuario=beto)

        suyo = Client()
        suyo.post('/login/', {'username': 'beto', 'password': 'clave-larga-2'})
        clave_de_beto = suyo.session.session_key

        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.client.post(reverse('sesiones_activas'), {'clave': clave_de_beto})

        self.assertTrue(SesionActiva.objects.filter(clave=clave_de_beto).exists())
        self.assertEqual(suyo.get(reverse('perfil')).status_code, 200)

    def test_salir_borra_la_fila(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.client.post(reverse('logout'))
        self.assertEqual(SesionActiva.objects.filter(usuario=self.ana).count(), 0)
