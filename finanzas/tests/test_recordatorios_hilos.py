from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from finanzas import push
from finanzas.models import SuscripcionPush, UserProfile

AVISO = {'titulo': 'Hoy vence Luz', 'cuerpo': 'Toca para verlo en Fintora.', 'url': '/',
         'etiqueta': 'cobros-hoy'}


@override_settings(VAPID_PRIVADA=push.generar_claves()[0])
class RecordatoriosEnParaleloTests(TransactionTestCase):

    def test_con_varios_hilos_avisa_a_todas_las_cuentas_una_vez(self):
        for i in range(5):
            usuario = User.objects.create_user(f'cuenta{i}', f'cuenta{i}@ejemplo.cl', 'clave-larga-1')
            SuscripcionPush.objects.create(usuario=usuario, p256dh='x', auth='y',
                                           endpoint=f'https://fcm.googleapis.com/fcm/send/{i}')
        salida = StringIO()
        with mock.patch('finanzas.management.commands.enviar_recordatorios.avisos_del_dia',
                        return_value=[AVISO]), \
                mock.patch.object(push, 'enviar_a_usuario', return_value=1) as enviar:
            call_command('enviar_recordatorios', '--hilos', '3', stdout=salida)
            call_command('enviar_recordatorios', '--hilos', '3', stdout=StringIO())
        self.assertEqual(enviar.call_count, 5)
        self.assertEqual(UserProfile.objects.filter(push_ultimo_dia=timezone.localdate()).count(), 5)
        self.assertIn('5 avisos a 5 personas', salida.getvalue())
