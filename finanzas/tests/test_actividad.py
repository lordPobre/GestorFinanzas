from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from finanzas import auditoria
from finanzas.models import EventoSeguridad


class ActividadCuentaTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@correo.cl', 'clave-larga-1')
        self.beto = User.objects.create_user('beto', 'beto@correo.cl', 'clave-larga-2')
        self.client.force_login(self.ana)

    def _cuerpo(self):
        respuesta = self.client.get(reverse('actividad_cuenta'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode('utf-8')

    def test_pide_sesion(self):
        self.client.logout()
        respuesta = self.client.get(reverse('actividad_cuenta'))
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta['Location'])

    def test_muestra_los_eventos_propios(self):
        auditoria.registrar('contrasena_cambiada', usuario=self.ana)
        auditoria.registrar('2fa_activada', usuario=self.ana)
        cuerpo = self._cuerpo()
        self.assertIn('Cambiaste la contraseña', cuerpo)
        self.assertIn('Activaste la verificación en dos pasos', cuerpo)

    def test_no_muestra_eventos_de_otra_persona(self):
        auditoria.registrar('datos_descargados', usuario=self.beto)
        auditoria.registrar('acceso_fallido', referencia='beto', detalle='contraseña')
        cuerpo = self._cuerpo()
        self.assertNotIn('Descargaste tus datos', cuerpo)
        self.assertNotIn('Contraseña incorrecta', cuerpo)

    def test_muestra_intentos_fallidos_con_su_usuario_o_correo(self):
        auditoria.registrar('acceso_fallido', referencia='ANA', detalle='contraseña')
        auditoria.registrar('bloqueo', referencia='ana@correo.cl', detalle='contraseña')
        cuerpo = self._cuerpo()
        self.assertIn('Contraseña incorrecta', cuerpo)
        self.assertIn('Acceso bloqueado por intentos', cuerpo)
        self.assertIn('¿Fuiste tú en todos los intentos fallidos?', cuerpo)

    def test_no_muestra_intentos_de_antes_de_crear_la_cuenta(self):
        auditoria.registrar('acceso_fallido', referencia='ana', detalle='contraseña')
        EventoSeguridad.objects.filter(tipo='acceso_fallido').update(
            creado=self.ana.date_joined - timedelta(days=1))
        self.assertNotIn('Contraseña incorrecta', self._cuerpo())

    def test_deja_fuera_lo_que_tiene_mas_de_noventa_dias(self):
        auditoria.registrar('datos_descargados', usuario=self.ana)
        User.objects.filter(pk=self.ana.pk).update(
            date_joined=timezone.now() - timedelta(days=400))
        EventoSeguridad.objects.filter(tipo='datos_descargados').update(
            creado=timezone.now() - timedelta(days=91))
        self.assertNotIn('Descargaste tus datos', self._cuerpo())

    def test_cuenta_las_entradas(self):
        EventoSeguridad.objects.all().delete()
        auditoria.registrar('acceso', usuario=self.ana, detalle='google')
        auditoria.registrar('acceso', usuario=self.ana, detalle='face_id_o_huella')
        cuerpo = self._cuerpo()
        self.assertIn('<span class="sec-monto">2</span>', cuerpo)
        self.assertIn('Con Google', cuerpo)
        self.assertIn('Con Face ID o huella', cuerpo)

    def test_no_trae_scripts_sin_nonce(self):
        for trozo in self._cuerpo().split('<script')[1:]:
            self.assertIn('nonce=', trozo.split('>')[0])
