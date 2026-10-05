from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from finanzas.models import Contador, SesionActiva


class Command(BaseCommand):
    help = 'Borra sesiones vencidas, contadores de intentos vencidos y sesiones activas sin sesión.'

    def handle(self, *args, **opciones):
        antes = Session.objects.count()
        call_command('clearsessions')
        sesiones = antes - Session.objects.count()

        contadores, _ = Contador.objects.filter(vence__lt=timezone.now()).delete()
        vivas = Session.objects.values('session_key')
        huerfanas, _ = SesionActiva.objects.exclude(clave__in=vivas).delete()

        self.stdout.write(self.style.SUCCESS(
            f'Limpieza: {sesiones} sesiones vencidas, {contadores} contadores y '
            f'{huerfanas} sesiones activas sin sesión.'))
