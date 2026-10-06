from django.core.management.base import BaseCommand

from finanzas import push


class Command(BaseCommand):
    help = 'Genera el par de claves VAPID para los recordatorios en el teléfono.'

    def handle(self, *args, **opciones):
        privada, publica = push.generar_claves()
        self.stdout.write('Pon esta variable en Railway y guárdala en un lugar seguro:')
        self.stdout.write(f'VAPID_PRIVADA={privada}')
        self.stdout.write('')
        self.stdout.write(f'Clave pública (se calcula sola, no hace falta guardarla): {publica}')
