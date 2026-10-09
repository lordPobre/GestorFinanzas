import json
from datetime import datetime, timezone as tz
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from ..management.commands.enviar_recordatorios import Command
from ..models import UserProfile
from ..views.recordatorios import zona_valida


class ZonaValidaTests(TestCase):

    def test_acepta_zonas_reales_y_rechaza_lo_demas(self):
        self.assertEqual(zona_valida('America/Santiago'), 'America/Santiago')
        self.assertEqual(zona_valida('Europe/Madrid'), 'Europe/Madrid')
        for malo in ('', 'UTC+3', 'Marte/Olympus', 'x' * 80, None):
            self.assertEqual(zona_valida(malo), '', malo)


class HoraLocalTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        self.perfil, _ = UserProfile.objects.get_or_create(usuario=self.ana)

    def test_la_hora_se_calcula_en_la_zona_de_cada_persona(self):
        ahora = datetime(2026, 1, 15, 12, 0, tzinfo=tz.utc)
        self.assertEqual(Command()._ahora_de(self.ana, ahora).hour, 9)
        self.perfil.zona_horaria = 'Europe/Madrid'
        self.perfil.save()
        self.assertEqual(Command()._ahora_de(self.ana, ahora).hour, 13)

    def test_una_zona_rota_cae_en_santiago(self):
        self.perfil.zona_horaria = 'Marte/Olympus'
        self.perfil.save()
        ahora = datetime(2026, 7, 15, 13, 0, tzinfo=tz.utc)
        self.assertEqual(Command()._ahora_de(self.ana, ahora).hour, 9)

    def test_con_a_las_solo_atiende_a_quien_le_toca(self):
        atendidos = []
        with patch('finanzas.push.disponible', return_value=True), \
             patch.object(Command, '_atender', lambda s, u, hoy, f: atendidos.append((u.pk, hoy)) or (False, 0)), \
             patch('finanzas.management.commands.enviar_recordatorios.User.objects') as usuarios, \
             patch('django.utils.timezone.now', return_value=datetime(2026, 1, 15, 12, 0, tzinfo=tz.utc)):
            usuarios.filter.return_value.distinct.return_value = [self.ana]
            call_command('enviar_recordatorios', '--a-las', '8', stdout=StringIO())
            self.assertEqual(atendidos, [])
            call_command('enviar_recordatorios', '--a-las', '9', stdout=StringIO())
        self.assertEqual(atendidos, [(self.ana.pk, datetime(2026, 1, 15).date())])


@override_settings(VAPID_PRIVADA='x', VAPID_PUBLICA='y')
class SuscribirGuardaLaZonaTests(TestCase):

    def setUp(self):
        self.ana = User.objects.create_user('ana', 'ana@ejemplo.cl', 'clave-larga-1')
        UserProfile.objects.get_or_create(usuario=self.ana)
        self.client.force_login(self.ana)

    def test_guarda_la_zona_que_manda_el_telefono(self):
        datos = {'endpoint': 'https://fcm.googleapis.com/fcm/send/abc',
                 'keys': {'p256dh': 'B' * 87, 'auth': 'a' * 22}, 'zona': 'Europe/Madrid'}
        with patch('finanzas.push.disponible', return_value=True), \
             patch('finanzas.push.endpoint_valido', return_value=True), \
             patch('finanzas.push.claves_validas', return_value=True):
            r = self.client.post(reverse('push_suscribir'), json.dumps(datos), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(UserProfile.objects.get(usuario=self.ana).zona_horaria, 'Europe/Madrid')
