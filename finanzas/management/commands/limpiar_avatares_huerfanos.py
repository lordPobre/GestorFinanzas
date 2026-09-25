from django.core.management.base import BaseCommand

from finanzas.almacenamiento import almacen_media
from finanzas.models import UserProfile


class Command(BaseCommand):
    help = 'Encuentra y opcionalmente borra avatares en el bucket que ningún perfil referencia.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--borrar', action='store_true',
            help='Borra los archivos huérfanos. Sin esta bandera solo los lista (dry-run).')

    def handle(self, *args, **options):
        referenciados = set(
            UserProfile.objects.exclude(foto='').exclude(foto__isnull=True)
                               .values_list('foto', flat=True)
        )

        huerfanos = []
        try:
            carpetas, _ = almacen_media.listdir('avatares')
        except FileNotFoundError:
            self.stdout.write('No existe la carpeta "avatares" en el bucket. Nada que revisar.')
            return

        for carpeta in carpetas:
            ruta_carpeta = f'avatares/{carpeta}'
            try:
                _, archivos = almacen_media.listdir(ruta_carpeta)
            except FileNotFoundError:
                continue
            for archivo in archivos:
                ruta = f'{ruta_carpeta}/{archivo}'
                if ruta not in referenciados:
                    huerfanos.append(ruta)

        if not huerfanos:
            self.stdout.write(self.style.SUCCESS('No hay avatares huérfanos.'))
            return

        if referenciados and len(huerfanos) >= (len(huerfanos) + len(referenciados)):
            self.stdout.write(self.style.ERROR(
                f'ABORTADO: los {len(huerfanos)} archivos del bucket aparecen como '
                f'huérfanos, pero la base referencia {len(referenciados)}. '
                'Eso indica que las rutas no coinciden (prefijo distinto), no que '
                'sobren archivos. Revisa cómo se comparan antes de borrar.'))
            self.stdout.write('\nRutas en el bucket (primeras 3):')
            for ruta in huerfanos[:3]:
                self.stdout.write(f'  {ruta}')
            self.stdout.write('Rutas en la base (primeras 3):')
            for ruta in list(referenciados)[:3]:
                self.stdout.write(f'  {ruta}')
            return

        self.stdout.write(f'{len(huerfanos)} archivo(s) huérfano(s):')
        for ruta in huerfanos:
            self.stdout.write(f'  {ruta}')

        if not options['borrar']:
            self.stdout.write(self.style.WARNING(
                '\nEsto fue solo una lista (dry-run). Vuelve a correr con --borrar para eliminarlos.'))
            return

        borrados = 0
        for ruta in huerfanos:
            try:
                almacen_media.delete(ruta)
                borrados += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  No se pudo borrar {ruta}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\n{borrados} archivo(s) borrado(s).'))
