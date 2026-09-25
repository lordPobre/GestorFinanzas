import json
from types import SimpleNamespace
from unittest.mock import patch

import pyotp
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from webauthn.helpers import bytes_to_base64url

from .. import google_login
from ..models import EventoSeguridad, Passkey, RespuestaEncuesta, SegundoFactor, UserProfile
from ..views.passkeys import _handle

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.create(usuario=self.ana)


class ContrasenaYCodigo(Base):
    def setUp(self):
        super().setUp()
        self.secreto = pyotp.random_base32()
        SegundoFactor.objects.create(usuario=self.ana, secreto=self.secreto, activo=True)

    def test_la_contrasena_sola_no_abre_la_sesion(self):
        respuesta = self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.assertRedirects(respuesta, reverse('verificar_codigo'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_con_el_codigo_correcto_entra(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.client.post(reverse('verificar_codigo'), {'codigo': pyotp.TOTP(self.secreto).now()})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.ana.pk)
        self.assertEqual(EventoSeguridad.objects.get(tipo='acceso').detalle, 'código de verificación')

    def test_con_un_codigo_malo_no_entra_y_queda_anotado(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.client.post(reverse('verificar_codigo'), {'codigo': '000000'})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(EventoSeguridad.objects.filter(tipo='codigo_fallido', usuario=self.ana).exists())

    def test_el_mismo_codigo_no_sirve_dos_veces(self):
        codigo = pyotp.TOTP(self.secreto).now()
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.client.post(reverse('verificar_codigo'), {'codigo': codigo})
        self.client.logout()
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.client.post(reverse('verificar_codigo'), {'codigo': codigo})
        self.assertNotIn('_auth_user_id', self.client.session)


class FaceIdOHuella(Base):
    def _passkey(self, usuario=None, cid='credencial-1'):
        return Passkey.objects.create(usuario=usuario or self.ana, credencial_id=cid,
                                      clave_publica=bytes_to_base64url(b'clave'), nombre='iPhone')

    def _credencial(self, cid='credencial-1', handle=None):
        return json.dumps({'id': cid, 'rawId': cid, 'type': 'public-key',
                           'response': {'userHandle': handle}})

    def test_vincular_pide_la_contrasena(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(reverse('passkey_registro_opciones'), {'password': 'mala'}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertNotIn('passkey_registro', self.client.session)

    def test_vincular_con_la_contrasena_entrega_un_desafio(self):
        self.client.force_login(self.ana)
        respuesta = self.client.post(reverse('passkey_registro_opciones'),
                                     {'password': 'clave-larga-1'}, **AJAX)
        datos = respuesta.json()
        self.assertTrue(datos['ok'])
        self.assertEqual(datos['opciones']['challenge'], self.client.session['passkey_registro'])
        self.assertEqual(datos['opciones']['authenticatorSelection']['userVerification'], 'required')

    def test_entrar_exige_verificar_a_la_persona(self):
        datos = self.client.post(reverse('passkey_entrar_opciones'), **AJAX).json()
        self.assertEqual(datos['opciones']['userVerification'], 'required')
        self.assertIn('passkey_reto', self.client.session)

    def test_sin_desafio_previo_se_rechaza(self):
        respuesta = self.client.post(reverse('passkey_entrar_verificar'),
                                     {'credencial': self._credencial()}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)

    def test_una_credencial_desconocida_se_rechaza_y_queda_anotada(self):
        self.client.post(reverse('passkey_entrar_opciones'), **AJAX)
        respuesta = self.client.post(reverse('passkey_entrar_verificar'),
                                     {'credencial': self._credencial('otra')}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(EventoSeguridad.objects.filter(tipo='passkey_fallida').exists())

    @patch('finanzas.views.passkeys.verify_authentication_response')
    def test_una_firma_valida_entra_sin_contrasena_ni_codigo(self, verificar):
        verificar.return_value = SimpleNamespace(new_sign_count=7)
        SegundoFactor.objects.create(usuario=self.ana, secreto=pyotp.random_base32(), activo=True)
        passkey = self._passkey()
        self.client.post(reverse('passkey_entrar_opciones'), **AJAX)
        handle = bytes_to_base64url(_handle(self.ana))
        datos = self.client.post(reverse('passkey_entrar_verificar'),
                                 {'credencial': self._credencial(handle=handle)}, **AJAX).json()
        self.assertTrue(datos['ok'])
        self.assertEqual(int(self.client.session['_auth_user_id']), self.ana.pk)
        passkey.refresh_from_db()
        self.assertEqual(passkey.contador, 7)
        self.assertIsNotNone(passkey.ultimo_uso)
        self.assertEqual(EventoSeguridad.objects.get(tipo='acceso').detalle, 'face_id_o_huella')

    @patch('finanzas.views.passkeys.verify_authentication_response')
    def test_una_firma_de_otra_cuenta_no_entra(self, verificar):
        verificar.return_value = SimpleNamespace(new_sign_count=1)
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        self._passkey()
        self.client.post(reverse('passkey_entrar_opciones'), **AJAX)
        ajeno = bytes_to_base64url(_handle(beto))
        respuesta = self.client.post(reverse('passkey_entrar_verificar'),
                                     {'credencial': self._credencial(handle=ajeno)}, **AJAX)
        self.assertEqual(respuesta.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_no_se_puede_quitar_la_de_otra_persona(self):
        beto = User.objects.create_user('beto', 'beto@ejemplo.cl', 'clave-larga-2')
        ajena = self._passkey(usuario=beto, cid='de-beto')
        self.client.force_login(self.ana)
        self.client.post(reverse('passkeys'), {'accion': 'eliminar', 'id': ajena.pk})
        self.assertTrue(Passkey.objects.filter(pk=ajena.pk).exists())


class Encuesta(Base):
    def _respuesta(self, **extra):
        datos = {'facilidad': '4', 'recomienda': '9', 'secciones': ['Inicio', 'Metas'],
                 'nota_0': '5', 'gusta': 'el resumen'}
        datos.update(extra)
        return datos

    def test_una_respuesta_completa_se_guarda(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('encuesta'), self._respuesta())
        r = RespuestaEncuesta.objects.get(usuario=self.ana)
        self.assertEqual(r.recomienda, 9)
        self.assertEqual(r.notas, {'Inicio': 5})

    def test_sin_las_obligatorias_no_se_guarda(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('encuesta'), self._respuesta(recomienda='', secciones=[]))
        self.assertFalse(RespuestaEncuesta.objects.exists())

    def test_una_nota_fuera_de_rango_no_se_guarda(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('encuesta'), self._respuesta(recomienda='15'))
        self.assertFalse(RespuestaEncuesta.objects.exists())

    def test_los_resultados_son_solo_para_el_personal(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('encuesta_resultados')).status_code, 404)

    def test_el_personal_descarga_el_csv(self):
        jefa = User.objects.create_user('jefa', 'jefa@ejemplo.cl', 'clave-larga-3', is_staff=True)
        RespuestaEncuesta.objects.create(usuario=self.ana, facilidad=4, recomienda=8, secciones=['Inicio'])
        self.client.force_login(jefa)
        respuesta = self.client.get(reverse('encuesta_resultados') + '?formato=csv')
        self.assertIn('text/csv', respuesta['Content-Type'])
        self.assertIn('Fecha', respuesta.content.decode('utf-8'))


@override_settings(GOOGLE_CLIENT_ID='cliente-de-prueba')
class TokenDeGoogle(TestCase):
    def _datos(self, **cambios):
        import time
        datos = {'iss': 'https://accounts.google.com', 'aud': 'cliente-de-prueba',
                 'exp': int(time.time()) + 600, 'sub': '123', 'email': 'ana@ejemplo.cl',
                 'email_verified': True}
        datos.update(cambios)
        return datos

    def test_acepta_un_token_valido(self):
        google_login._validar(self._datos())

    def test_rechaza_un_correo_sin_verificar(self):
        with self.assertRaises(ValueError):
            google_login._validar(self._datos(email_verified=False))

    def test_rechaza_un_token_de_otra_aplicacion(self):
        with self.assertRaises(ValueError):
            google_login._validar(self._datos(aud='otra-app'))

    def test_rechaza_un_token_vencido(self):
        with self.assertRaises(ValueError):
            google_login._validar(self._datos(exp=1))

    def test_rechaza_otro_emisor(self):
        with self.assertRaises(ValueError):
            google_login._validar(self._datos(iss='https://falso.example'))


class PantallaDeCartolas(Base):
    def test_carga_con_sesion(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('importar_cartola')).status_code, 200)

    def test_sin_sesion_pide_entrar(self):
        respuesta = self.client.get(reverse('importar_cartola'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])
