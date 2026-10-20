from django.core.management.base import BaseCommand
from django.db import transaction

from ...servicios.vinculo_categoria import arreglar, revisar


class Command(BaseCommand):
    help = 'Revisa que ninguna fila apunte a una categoría propia de otra cuenta.'

    def add_arguments(self, parser):
        parser.add_argument('--arreglar', action='store_true',
                            help='Vuelve a vincular las filas que apuntan a una categoría de otra cuenta.')

    def handle(self, *args, **opciones):
        if opciones['arreglar']:
            with transaction.atomic():
                n = arreglar()
            self.stdout.write(f'Filas arregladas: {n}')
        problemas = 0
        for fila in revisar():
            problemas += fila['desalineados']
            self.stdout.write(f"{fila['tabla']}: {fila['total']} filas, {fila['desalineados']} que no calzan")
        if problemas:
            self.stdout.write(self.style.WARNING(f'Quedan {problemas} filas por revisar.'))
        else:
            self.stdout.write(self.style.SUCCESS('Todo vinculado.'))
