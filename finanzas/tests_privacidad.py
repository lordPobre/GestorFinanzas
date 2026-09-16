"""Tests de las obligaciones de privacidad.

Lo que se comprueba acá es lo que un auditor pediría ver funcionando:

  · Las páginas legales son públicas. Si pidieran sesión, quien está
    decidiendo si se registra no podría leer a qué se compromete.
  · Nadie se da de alta sin aceptar, y la aceptación queda con versión y
    fecha, no como un sí suelto.
  · El interruptor del análisis con IA se respeta en el servidor. Si solo
    se respetara en el navegador, una llamada directa a la URL seguiría
    mandando datos al tercero.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from . import legal
from .models import Transaccion, UserProfile

class PaginasLegales(TestCase):
    def test_son_publicas(self):
        for nombre in ('privacidad', 'terminos'):
            respuesta = self.client.get(reverse(nombre))
            self.assertEqual(respuesta.status_code, 200, nombre)

    def test_nombran_al_responsable_y_el_contacto(self):
        cuerpo = self.client.get(reverse('privacidad')).content.decode('utf-8')
        self.assertIn(legal.CORREO_CONTACTO, cuerpo)
        self.assertIn('Carlos López Figueroa', cuerpo)

    def test_declaran_la_version_vigente(self):
        cuerpo = self.client.get(reverse('terminos')).content.decode('utf-8')
        self.assertIn(legal.VERSION, cuerpo)

class ConsentimientoEnElAlta(TestCase):
    URL = '/registro/'

    def _datos(self, **extra):
        datos = {
            'username': 'nueva',
            'email_perfil': 'nueva@ejemplo.cl',
            'password1': 'contrasena-larga-77',
            'password2': 'contrasena-larga-77',
            'nombre_completo': 'Persona Nueva',
        }
        datos.update(extra)
        return datos

    def test_sin_aceptar_no_se_crea_la_cuenta(self):
        self.client.post(self.URL, self._datos())
        self.assertFalse(User.objects.filter(username='nueva').exists())

    def test_aceptando_se_crea_y_queda_registrado(self):
        self.client.post(self.URL, self._datos(acepta_politica='1'))

        usuario = User.objects.filter(username='nueva').first()
        self.assertIsNotNone(usuario)

        perfil = UserProfile.objects.get(usuario=usuario)
        self.assertEqual(perfil.politica_version, legal.VERSION)
        self.assertIsNotNone(perfil.politica_aceptada)

class OposicionAlAnalisisConIA(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil = UserProfile.objects.create(usuario=self.ana)
        Transaccion.objects.create(usuario=self.ana, tipo='INGRESO',
                                   monto=Decimal('800000'), categoria='Sueldo',
                                   fecha=date.today())
        self.client.force_login(self.ana)

    def test_apagado_el_servidor_no_llama_a_la_ia(self):
        self.perfil.analisis_ia = False
        self.perfil.save(update_fields=['analisis_ia'])

        llamadas = []

        import finanzas.ia as modulo_ia
        original = modulo_ia.interpretar_con_ia
        modulo_ia.interpretar_con_ia = lambda *a, **k: llamadas.append(1)
        try:
            respuesta = self.client.get(reverse('analisis_ia'))
        finally:
            modulo_ia.interpretar_con_ia = original

        self.assertEqual(llamadas, [])
        self.assertFalse(respuesta.json()['ok'])
        self.assertTrue(respuesta.json().get('desactivado'))

    def test_el_interruptor_se_guarda(self):
        self.client.post(reverse('perfil'), {'accion': 'analisis_ia', 'activar': '0'})
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.analisis_ia)

        self.client.post(reverse('perfil'), {'accion': 'analisis_ia', 'activar': '1'})
        self.perfil.refresh_from_db()
        self.assertTrue(self.perfil.analisis_ia)

class RegistroDeActividad(TestCase):
    """El campo sobre el que se medirá la inactividad tiene que escribirse
    solo, o el plazo de conservación declarado no se puede aplicar."""

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.create(usuario=self.ana)

    def test_navegar_deja_marca(self):
        self.client.force_login(self.ana)
        self.client.get(reverse('perfil'))

        perfil = UserProfile.objects.get(usuario=self.ana)
        self.assertIsNotNone(perfil.ultima_actividad)

    def test_sin_sesion_no_escribe_nada(self):
        self.client.get(reverse('privacidad'))
        perfil = UserProfile.objects.get(usuario=self.ana)
        self.assertIsNone(perfil.ultima_actividad)
