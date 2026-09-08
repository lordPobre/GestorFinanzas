"""Respaldo de la base de datos SQLite, seguro sobre una base en uso.

    python manage.py respaldar
    python manage.py respaldar --destino /home/usuario/respaldos --conservar 14

Por qué existe un comando y no un `cp db.sqlite3 copia.sqlite3`:

Copiar el archivo con el sistema operativo mientras la aplicación corre da
una copia rota con más frecuencia de la que uno esperaría. En modo WAL —que
es como corre esta app— las escrituras recientes viven en `db.sqlite3-wal`,
un archivo aparte. Copiar solo el `.sqlite3` deja fuera todo lo que no se ha
consolidado todavía; copiar los tres archivos por separado los captura en
instantes distintos y el resultado puede ser incoherente.

La API de respaldo de SQLite (`Connection.backup`) resuelve justamente eso:
toma una instantánea consistente de la base en uso, sin bloquear a quien
está escribiendo y sin depender de en qué archivo esté cada página.

Después de escribir la copia se abre y se le corre `PRAGMA integrity_check`,
y se cuenta cuántos usuarios y movimientos tiene. Un respaldo que no se
verifica no es un respaldo: es un archivo del que uno se entera de que está
vacío el día que lo necesita.
"""
import gzip
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea una copia verificada de la base SQLite y rota las antiguas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destino',
            help='Carpeta donde dejar la copia. Por defecto, respaldos/ junto '
                 'al proyecto, o la variable de entorno RESPALDOS_DIR.',
        )
        parser.add_argument(
            '--conservar', type=int, default=14,
            help='Cuántas copias mantener. Las más antiguas se borran. '
                 'Por defecto 14.',
        )
        parser.add_argument(
            '--sin-comprimir', action='store_true',
            help='Deja el .sqlite3 tal cual en vez de comprimirlo con gzip.',
        )

    def handle(self, *args, **opciones):
        ruta_origen = self._ruta_base()
        destino = self._carpeta_destino(opciones.get('destino'))
        destino.mkdir(parents=True, exist_ok=True)

        marca = datetime.now().strftime('%Y%m%d-%H%M%S')
        ruta_cruda = destino / f'finapp-{marca}.sqlite3'

        self.stdout.write(f'Origen:  {ruta_origen}')
        self.stdout.write(f'Destino: {ruta_cruda}')

        self._copiar(ruta_origen, ruta_cruda)
        resumen = self._verificar(ruta_cruda)

        final = ruta_cruda
        if not opciones['sin_comprimir']:
            final = self._comprimir(ruta_cruda)

        tam = final.stat().st_size
        self.stdout.write(self.style.SUCCESS(
            f'Copia verificada: {final.name} '
            f'({tam / 1024 / 1024:.2f} MB, {resumen})'
        ))

        borradas = self._rotar(destino, opciones['conservar'])
        if borradas:
            self.stdout.write(f'Rotación: {borradas} copia(s) antigua(s) eliminada(s).')

    # ------------------------------------------------------------------

    def _ruta_base(self):
        config = settings.DATABASES['default']
        if 'sqlite' not in config['ENGINE']:
            raise CommandError(
                'Este comando respalda SQLite y la base configurada no lo es.\n'
                'Con PostgreSQL el respaldo se hace con pg_dump, o con las '
                'copias automáticas del proveedor. Ver RESPALDOS.md.'
            )
        ruta = Path(config['NAME'])
        if not ruta.exists():
            raise CommandError(f'No existe el archivo de base de datos: {ruta}')
        return ruta

    def _carpeta_destino(self, indicado):
        if indicado:
            return Path(indicado).expanduser()
        del_entorno = os.environ.get('RESPALDOS_DIR')
        if del_entorno:
            return Path(del_entorno).expanduser()
        return Path(settings.BASE_DIR) / 'respaldos'

    def _copiar(self, origen, destino):
        """Instantánea consistente con la API de respaldo de SQLite.

        Se abre el origen en modo solo lectura (URI con mode=ro) para no
        arriesgar ninguna escritura accidental sobre la base en producción.
        """
        con_origen = sqlite3.connect(f'file:{origen}?mode=ro', uri=True, timeout=30)
        try:
            con_destino = sqlite3.connect(destino)
            try:
                # pages=0 copia todo de una vez. Para bases grandes se puede
                # trocear con pages=N y un callback de progreso; a esta escala
                # no compensa la complejidad.
                con_origen.backup(con_destino)
            finally:
                con_destino.close()
        finally:
            con_origen.close()

    def _verificar(self, ruta):
        """Abre la copia y comprueba que sirve. Si no, la borra y falla.

        Dejar una copia corrupta en la carpeta es peor que no tenerla: da
        una falsa sensación de respaldo hasta el día de la restauración.
        """
        con = sqlite3.connect(f'file:{ruta}?mode=ro', uri=True)
        try:
            resultado = con.execute('PRAGMA integrity_check').fetchone()
            if not resultado or resultado[0] != 'ok':
                ruta.unlink(missing_ok=True)
                raise CommandError(f'La copia no pasó integrity_check: {resultado}')

            usuarios = con.execute('SELECT COUNT(*) FROM auth_user').fetchone()[0]
            movimientos = con.execute(
                'SELECT COUNT(*) FROM finanzas_transaccion').fetchone()[0]

            if usuarios == 0:
                # Una base sin un solo usuario casi siempre significa que se
                # respaldó el archivo equivocado.
                self.stdout.write(self.style.WARNING(
                    'Aviso: la copia no tiene ningún usuario. '
                    '¿Es la base correcta?'))

            return f'{usuarios} usuarios, {movimientos} movimientos'
        except sqlite3.DatabaseError as e:
            ruta.unlink(missing_ok=True)
            raise CommandError(f'La copia no se puede leer: {e}')
        finally:
            con.close()

    def _comprimir(self, ruta):
        destino = ruta.with_suffix('.sqlite3.gz')
        with open(ruta, 'rb') as entrada, gzip.open(destino, 'wb', compresslevel=6) as salida:
            shutil.copyfileobj(entrada, salida)
        ruta.unlink()
        return destino

    def _rotar(self, carpeta, conservar):
        """Deja solo las N copias más recientes."""
        if conservar <= 0:
            return 0
        copias = sorted(
            [p for p in carpeta.iterdir()
             if p.name.startswith('finapp-') and '.sqlite3' in p.name],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        sobrantes = copias[conservar:]
        for p in sobrantes:
            p.unlink()
        return len(sobrantes)
