import re

from django.core.management.base import BaseCommand, CommandError

from ...ia_cliente import uso_del_mes


def _miles(n):
    return f'{n:,}'.replace(',', '.')


class Command(BaseCommand):
    help = 'Muestra las llamadas a la IA del mes: cuántas, cuántas fallaron, tokens, demora y costo estimado.'

    def add_arguments(self, parser):
        parser.add_argument('--mes', help='Mes en formato AAAA-MM. Por defecto, el actual.')

    def handle(self, *args, **opciones):
        mes = (opciones.get('mes') or '').strip() or None
        if mes and not re.fullmatch(r'\d{4}-\d{2}', mes):
            raise CommandError('El mes va como AAAA-MM, por ejemplo 2026-10.')
        filas = uso_del_mes(mes)
        if not filas:
            self.stdout.write('No hubo llamadas a la IA ese mes.')
            return
        total = 0.0
        for f in filas:
            promedio = f['ms'] // f['llamadas'] if f['llamadas'] else 0
            costo = f"US${f['dolares']:.4f}" if f['dolares'] is not None else 'sin precio conocido'
            self.stdout.write(
                f"{f['funcion']} · {f['modelo']}: {f['llamadas']} llamadas, {f['fallos']} fallidas, "
                f"{f['invalidas']} sin formato, {_miles(f['entrada'])} tokens de entrada y "
                f"{_miles(f['salida'])} de salida, {promedio} ms en promedio, {costo}")
            total += f['dolares'] or 0
        self.stdout.write(f'Total estimado: US${total:.4f}')
