from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..comprobaciones import defusedxml_instalado
from ..management.commands import respaldar_postgres
from ..models import Contador, SesionActiva


@override_settings(DOMINIO_CANONICO='fintora.cl', ALLOWED_HOSTS=['fintora.cl', 'otro.up.railway.app',
                                                                  'healthcheck.railway.app'])
class DominioCanonicoTests(TestCase):

    def test_otro_dominio_redirige_al_canonico(self):
        r = self.client.get('/privacidad/?a=1', HTTP_HOST='otro.up.railway.app')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], 'https://fintora.cl/privacidad/?a=1')

    def test_post_conserva_el_metodo(self):
        r = self.client.post('/login/', HTTP_HOST='otro.up.railway.app')
        self.assertEqual(r.status_code, 308)

    def test_salud_y_healthcheck_no_redirigen(self):
        self.assertNotEqual(self.client.get('/salud/', HTTP_HOST='otro.up.railway.app').status_code, 301)
        r = self.client.get('/privacidad/', HTTP_HOST='healthcheck.railway.app')
        self.assertNotEqual(r.status_code, 301)

    @override_settings(ALLOWED_HOSTS=['fintora.cl'])
    def test_un_host_fuera_de_la_lista_tambien_redirige(self):
        r = self.client.get('/', HTTP_HOST='fintora.up.railway.app')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], 'https://fintora.cl/')

    def test_el_canonico_pasa(self):
        self.assertEqual(self.client.get('/privacidad/', HTTP_HOST='fintora.cl').status_code, 200)


class LimpiezaDiariaTests(TestCase):

    def test_borra_lo_vencido_y_deja_lo_vivo(self):
        ana = User.objects.create_user('ana', password='x')
        viva = SessionStore()
        viva['a'] = 1
        viva.create()
        vieja = SessionStore()
        vieja['a'] = 1
        vieja.create()
        Session.objects.filter(session_key=vieja.session_key).update(
            expire_date=timezone.now() - timedelta(days=1))
        SesionActiva.objects.create(usuario=ana, clave=viva.session_key)
        SesionActiva.objects.create(usuario=ana, clave='no-existe')
        Contador.objects.create(clave='viejo', cuenta=3,
                                vence=timezone.now() - timedelta(minutes=1))
        Contador.objects.create(clave='vivo', cuenta=3,
                                vence=timezone.now() + timedelta(minutes=10))

        call_command('limpieza_diaria', stdout=StringIO())

        self.assertTrue(Session.objects.filter(session_key=viva.session_key).exists())
        self.assertFalse(Session.objects.filter(session_key=vieja.session_key).exists())
        self.assertEqual(list(SesionActiva.objects.values_list('clave', flat=True)), [viva.session_key])
        self.assertEqual(list(Contador.objects.values_list('clave', flat=True)), ['vivo'])


class RespaldoTests(TestCase):

    def test_pg_dump_salta_sesiones_cache_y_contadores(self):
        with mock.patch.object(respaldar_postgres.subprocess, 'run') as correr:
            respaldar_postgres.Command()._volcar('pg_dump', {}, '/tmp/x.dump')
        orden = correr.call_args[0][0]
        for tabla in ('django_session', 'cache_finapp', 'finanzas_contador'):
            self.assertIn(f'--exclude-table-data={tabla}', orden)


class DefusedxmlTests(TestCase):

    def test_esta_instalado(self):
        self.assertEqual(defusedxml_instalado(None), [])

    def test_openpyxl_lo_usa(self):
        from openpyxl.xml import DEFUSEDXML
        self.assertTrue(DEFUSEDXML)


class DiagnosticoIpTests(TestCase):

    def test_solo_para_el_personal(self):
        self.assertEqual(self.client.get(reverse('diagnostico_ip')).status_code, 404)
        self.client.force_login(User.objects.create_user('ana', password='x'))
        self.assertEqual(self.client.get(reverse('diagnostico_ip')).status_code, 404)

    @override_settings(PROXIES_CONFIABLES=1)
    def test_sugiere_dos_saltos_detras_de_cloudflare(self):
        self.client.force_login(User.objects.create_user('jefa', password='x', is_staff=True))
        r = self.client.get(reverse('diagnostico_ip'), HTTP_X_FORWARDED_FOR='190.5.5.5, 172.68.1.1',
                            HTTP_CF_CONNECTING_IP='190.5.5.5')
        datos = r.json()
        self.assertEqual(datos['ip_usada'], '172.68.1.1')
        self.assertFalse(datos['coincide_con_cloudflare'])
        self.assertEqual(datos['proxies_confiables_sugerido'], 2)
