from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from ... import telegram


class Command(BaseCommand):
    help = 'Registra el webhook y los comandos del bot de Telegram.'

    def add_arguments(self, parser):
        parser.add_argument('--sitio', default='https://fintora.cl')

    def handle(self, *args, **opciones):
        if not telegram.configurado():
            raise CommandError('Faltan TELEGRAM_TOKEN, TELEGRAM_BOT o TELEGRAM_SECRETO.')
        url = opciones['sitio'].rstrip('/') + reverse('telegram_webhook')
        if telegram.llamar('setWebhook', url=url, secret_token=telegram.secreto(),
                           allowed_updates=['message', 'callback_query'], drop_pending_updates=True) is None:
            raise CommandError('Telegram no aceptó el webhook. Revisa el token.')
        telegram.llamar('setMyCommands', commands=[
            {'command': 'ayuda', 'description': 'Cómo anotar'},
            {'command': 'desconectar', 'description': 'Desconectar este chat de Fintora'},
        ])
        self.stdout.write(self.style.SUCCESS(f'Bot listo. Telegram avisa a {url}'))
