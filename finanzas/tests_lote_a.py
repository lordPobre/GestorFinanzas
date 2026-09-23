from datetime import date, timedelta
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from core.urls import entrada_admin

from . import auditoria
from .models import EventoSeguridad, SegundoFactor, Transaccion, UserProfile
from .seguridad import (MAX_INTENTOS, MAX_POR_CUENTA, MAX_POR_IP, esta_bloqueado,
                        limpiar_intentos, registrar_fallo)
from .views import resumen_mes

urlpatterns = [
    path('panel-prueba/', admin.site.urls),
    path('', include('finanzas.urls')),
]


@override_settings(ROOT_URLCONF='finanzas.tests_lote_a')
class PanelPorElAccesoNormal(TestCase):
    def setUp(self):
        cache.clear()
        self.jefa = User.objects.create_user('jefa', 'jefa@ejemplo.cl', 'clave-larga-1', is_staff=True,
                                             is_superuser=True)
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')

    def test_el_login_del_panel_es_el_propio(self):
        self.assertIs(admin.site.login, entrada_admin)

    def test_sin_sesion_manda_al_acceso_de_la_app(self):
        respuesta = self.client.get('/panel-prueba/login/?next=/panel-prueba/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith(reverse('login')))
        self.assertIn('next=/panel-prueba/', respuesta['Location'])

    def test_el_formulario_del_panel_no_inicia_sesion(self):
        SegundoFactor.objects.create(usuario=self.jefa, secreto='JBSWY3DPEHPK3PXP', activo=True)
        self.client.post('/panel-prueba/login/', {'username': 'jefa', 'password': 'clave-larga-1'})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_una_cuenta_sin_permiso_recibe_404_y_queda_anotado(self):
        self.client.force_login(self.ana)
        respuesta = self.client.get('/panel-prueba/login/')
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(EventoSeguridad.objects.filter(tipo='admin_denegado', usuario=self.ana).exists())

    def test_el_personal_entra(self):
        self.client.force_login(self.jefa)
        self.assertEqual(self.client.get('/panel-prueba/').status_code, 200)


class TopesDeIntentos(TestCase):
    def setUp(self):
        cache.clear()

    def test_el_par_usuario_ip_sigue_en_cinco(self):
        for _ in range(MAX_INTENTOS):
            registrar_fallo('ana', '10.0.0.1')
        self.assertGreater(esta_bloqueado('ana', '10.0.0.1'), 0)
        self.assertEqual(esta_bloqueado('ana', '10.0.0.2'), 0)

    def test_cambiar_de_ip_no_salta_el_tope_de_la_cuenta(self):
        for i in range(MAX_POR_CUENTA):
            registrar_fallo('ana', f'10.0.{i}.1')
        self.assertGreater(esta_bloqueado('ana', '192.168.0.9'), 0)
        self.assertEqual(esta_bloqueado('beto', '192.168.0.9'), 0)

    def test_una_ip_contra_muchas_cuentas_se_frena(self):
        for i in range(MAX_POR_IP):
            registrar_fallo(f'cuenta{i}', '10.9.9.9')
        self.assertGreater(esta_bloqueado('otra', '10.9.9.9'), 0)
        self.assertEqual(esta_bloqueado('otra', '10.9.9.8'), 0)

    def test_entrar_bien_no_limpia_el_contador_de_la_ip(self):
        for i in range(MAX_POR_IP):
            registrar_fallo(f'cuenta{i}', '10.9.9.9')
        limpiar_intentos('mia', '10.9.9.9')
        self.assertGreater(esta_bloqueado('otra', '10.9.9.9'), 0)

    def test_con_la_cuenta_bloqueada_la_contrasena_correcta_no_entra(self):
        User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        for i in range(MAX_POR_CUENTA):
            registrar_fallo('ana', f'10.0.{i}.1')
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.assertNotIn('_auth_user_id', self.client.session)


class EventosDeSeguridad(TestCase):
    def setUp(self):
        cache.clear()
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.create(usuario=self.ana)

    def test_entrar_queda_anotado(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'clave-larga-1'})
        evento = EventoSeguridad.objects.get(tipo='acceso')
        self.assertEqual(evento.usuario, self.ana)
        self.assertEqual(evento.detalle, 'contraseña')

    def test_fallar_queda_anotado_con_el_nombre_intentado(self):
        self.client.post('/login/', {'username': 'ana', 'password': 'otra-cosa'})
        evento = EventoSeguridad.objects.get(tipo='acceso_fallido')
        self.assertEqual(evento.referencia, 'ana')
        self.assertIsNone(evento.usuario)

    def test_la_descarga_de_datos_incluye_los_eventos(self):
        self.client.force_login(self.ana)
        auditoria.registrar('contrasena_cambiada', usuario=self.ana)
        datos = self.client.get(reverse('mis_datos')).json()
        tipos = [e['tipo'] for e in datos['eventos_de_seguridad']]
        self.assertIn('contrasena_cambiada', tipos)
        self.assertTrue(EventoSeguridad.objects.filter(tipo='datos_descargados').exists())

    def test_borrar_la_cuenta_deja_la_evidencia_sin_vinculo(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('eliminar_cuenta'),
                         {'confirmacion': 'ELIMINAR', 'password': 'clave-larga-1'})
        evento = EventoSeguridad.objects.get(tipo='cuenta_eliminada')
        self.assertIsNone(evento.usuario)
        self.assertEqual(evento.referencia, 'ana')

    def test_purgar_borra_solo_lo_de_mas_de_un_ano(self):
        auditoria.registrar('acceso', usuario=self.ana)
        auditoria.registrar('salida', usuario=self.ana)
        EventoSeguridad.objects.filter(tipo='acceso').update(
            creado=timezone.now() - timedelta(days=auditoria.DIAS_CONSERVACION + 1))
        self.assertEqual(auditoria.purgar(), 1)
        self.assertEqual(list(EventoSeguridad.objects.values_list('tipo', flat=True)), ['salida'])

    def test_con_dos_pasos_el_destino_no_se_pierde(self):
        SegundoFactor.objects.create(usuario=self.ana, secreto='JBSWY3DPEHPK3PXP', activo=True)
        self.client.post('/login/?next=/metas/', {'username': 'ana', 'password': 'clave-larga-1'})
        self.assertEqual(self.client.session.get('2fa_next'), '/metas/')


class MontosExactos(TestCase):
    def test_las_sumas_del_mes_no_arrastran_error_de_coma_flotante(self):
        ana = User.objects.create_user('ana', password='x')
        hoy = date.today()
        for monto in ('0.10', '0.20', '0.10', '0.20', '0.10', '0.20'):
            Transaccion.objects.create(usuario=ana, tipo='EGRESO', monto=Decimal(monto),
                                       categoria='Comida', fecha=hoy)
        r = resumen_mes(ana, hoy.year, hoy.month)
        self.assertIsInstance(r['exacto']['gastos'], Decimal)
        self.assertEqual(r['exacto']['gastos'], Decimal('0.90'))
        self.assertEqual(r['exacto']['disponible'], Decimal('-0.90'))
