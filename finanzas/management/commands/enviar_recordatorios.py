import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from finanzas import push
from finanzas.models import UserProfile
from finanzas.servicios.recordatorios import avisos_del_dia
from finanzas.views.comun import simbolo_de

logger = logging.getLogger('finanzas')


class Command(BaseCommand):
    help = 'Manda los recordatorios del día a los aparatos que los activaron.'

    def add_arguments(self, parser):
        parser.add_argument('--forzar', action='store_true',
                            help='Manda aunque ya se haya enviado hoy.')

    def handle(self, *args, **opciones):
        if not push.disponible():
            self.stdout.write(self.style.WARNING('Falta VAPID_PRIVADA: no se manda nada.'))
            return
        hoy = timezone.localdate()
        usuarios = User.objects.filter(suscripciones_push__isnull=False, is_active=True).distinct()
        personas = enviados = 0
        for usuario in usuarios:
            perfil, _ = UserProfile.objects.get_or_create(usuario=usuario)
            if perfil.push_ultimo_dia == hoy and not opciones['forzar']:
                continue
            try:
                avisos = avisos_del_dia(usuario, perfil, hoy, simbolo_de(usuario))
                for aviso in avisos:
                    enviados += push.enviar_a_usuario(usuario, aviso)
            except Exception:
                logger.exception('No se pudieron armar los recordatorios del usuario %s', usuario.pk)
                continue
            perfil.push_ultimo_dia = hoy
            perfil.save(update_fields=['push_ultimo_dia'])
            if avisos:
                personas += 1
        self.stdout.write(self.style.SUCCESS(
            f'Recordatorios: {enviados} avisos a {personas} persona{"s" if personas != 1 else ""}.'))
