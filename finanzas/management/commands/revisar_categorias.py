from django.core.management.base import BaseCommand
from django.db import transaction

from ...servicios.vinculo_categoria import arreglar, revisar


class Command(BaseCommand):
    help = 'Revisa que cada fila tenga su categoría vinculada a la tabla de categorías.'

    def add_arguments(self, parser):
        parser.add_argument('--arreglar', action='store_true',
                            help='Vuelve a vincular las filas sin vínculo o con un vínculo que no calza.')

    def handle(self, *args, **opciones):
        if opciones['arreglar']:
            with transaction.atomic():
                n = arreglar()
            self.stdout.write(f'Filas vinculadas: {n}')
        problemas = 0
        for fila in revisar():
            problemas += fila['sin_vinculo'] + fila['desalineados']
            linea = (f"{fila['tabla']}: {fila['total']} filas, {fila['sin_vinculo']} sin vínculo, "
                     f"{fila['desalineados']} que no calzan")
            if fila['textos_sueltos']:
                linea += ' (textos: ' + ', '.join(fila['textos_sueltos'][:20]) + ')'
            self.stdout.write(linea)
        if problemas:
            self.stdout.write(self.style.WARNING(f'Quedan {problemas} filas por revisar.'))
        else:
            self.stdout.write(self.style.SUCCESS('Todo vinculado.'))
