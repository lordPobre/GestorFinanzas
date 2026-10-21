from django.core.management.base import BaseCommand

from finanzas.voz import VIDA_EN_R2, limpiar_audios


class Command(BaseCommand):
    help = 'Borra de R2 los audios de la esfera con más de cinco horas.'

    def handle(self, *args, **opciones):
        borrados = limpiar_audios()
        horas = int(VIDA_EN_R2.total_seconds() // 3600)
        self.stdout.write(self.style.SUCCESS(f'Audios de más de {horas} horas borrados: {borrados}.'))
