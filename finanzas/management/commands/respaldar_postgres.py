import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

PREFIJO = 'postgres/'
TABLAS_OBLIGATORIAS = ('auth_user', 'finanzas_transaccion', 'finanzas_userprofile')


class Command(BaseCommand):
    help = 'Copia verificada de la base Postgres, subida a un bucket privado de R2.'

    def add_arguments(self, parser):
        parser.add_argument('--conservar', type=int, default=30,
                            help='Cuántas copias dejar en el bucket (por defecto 30).')
        parser.add_argument('--destino', default='',
                            help='Carpeta local donde dejar la copia en vez de subirla.')
        parser.add_argument('--seco', action='store_true',
                            help='Hace y verifica la copia pero no la sube ni rota nada.')

    def handle(self, *args, **opciones):
        base = settings.DATABASES['default']
        if 'postgresql' not in base['ENGINE']:
            raise CommandError('Este comando es para Postgres. Con SQLite usa "manage.py respaldar".')

        pg_dump = shutil.which('pg_dump')
        pg_restore = shutil.which('pg_restore')
        if not pg_dump or not pg_restore:
            raise CommandError('No están pg_dump ni pg_restore en esta imagen. Ver docs/RESPALDOS.md.')

        self._comparar_versiones(pg_dump)
        entorno = self._entorno(base)
        marca = timezone.now().strftime('%Y%m%d-%H%M%S')
        nombre = f'rekon-{marca}.dump'

        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / nombre
            self._volcar(pg_dump, entorno, ruta)
            tablas = self._verificar(pg_restore, ruta)
            tamano = ruta.stat().st_size
            huella = self._sha256(ruta)
            self.stdout.write(f'Copia verificada: {nombre}, {tamano / 1_048_576:.1f} MB, '
                              f'{tablas} tablas con datos, sha256 {huella[:16]}…')

            if opciones['seco']:
                self.stdout.write(self.style.WARNING('Simulación: no se subió ni se rotó nada.'))
                return

            if opciones['destino']:
                destino = Path(opciones['destino'])
                destino.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ruta, destino / nombre)
                self.stdout.write(self.style.SUCCESS(f'Guardada en {destino / nombre}'))
                return

            cliente, bucket = self._r2()
            clave = PREFIJO + nombre
            cliente.upload_file(str(ruta), bucket, clave, ExtraArgs={
                'ContentType': 'application/octet-stream',
                'Metadata': {'sha256': huella, 'tablas': str(tablas)},
            })
            self.stdout.write(self.style.SUCCESS(f'Subida a r2://{bucket}/{clave}'))
            borradas = self._rotar(cliente, bucket, opciones['conservar'])
            if borradas:
                self.stdout.write(f'Rotación: {borradas} copia(s) antigua(s) borrada(s).')

    def _comparar_versiones(self, pg_dump):
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SHOW server_version_num')
            servidor = int(cur.fetchone()[0]) // 10000
        texto = subprocess.run([pg_dump, '--version'], check=True, capture_output=True,
                               timeout=30).stdout.decode(errors='replace')
        numeros = [p for p in texto.split() if p[:1].isdigit()]
        cliente = int(numeros[0].split('.')[0]) if numeros else 0
        self.stdout.write(f'Postgres del servidor: {servidor} · pg_dump: {cliente}')
        if cliente < servidor:
            raise CommandError(
                f'pg_dump {cliente} no puede copiar un servidor {servidor}. En el servicio del '
                f'respaldo usa /railway/respaldo.json y la variable PG_MAJOR={servidor}. '
                'Ver docs/RESPALDOS.md.')

    def _entorno(self, base):
        entorno = os.environ.copy()
        entorno.update({
            'PGHOST': str(base.get('HOST') or ''),
            'PGPORT': str(base.get('PORT') or '5432'),
            'PGUSER': str(base.get('USER') or ''),
            'PGPASSWORD': str(base.get('PASSWORD') or ''),
            'PGDATABASE': str(base.get('NAME') or ''),
        })
        modo = (base.get('OPTIONS') or {}).get('sslmode')
        if modo:
            entorno['PGSSLMODE'] = modo
        return entorno

    def _volcar(self, pg_dump, entorno, ruta):
        orden = [pg_dump, '--format=custom', '--compress=6', '--no-owner',
                 '--no-privileges', f'--file={ruta}']
        try:
            subprocess.run(orden, env=entorno, check=True, capture_output=True, timeout=1800)
        except subprocess.CalledProcessError as e:
            raise CommandError('pg_dump falló: ' + e.stderr.decode(errors='replace')[-800:])
        except subprocess.TimeoutExpired:
            raise CommandError('pg_dump tardó más de 30 minutos y se cortó.')

    def _verificar(self, pg_restore, ruta):
        try:
            salida = subprocess.run([pg_restore, '--list', str(ruta)], check=True,
                                    capture_output=True, timeout=300).stdout.decode(errors='replace')
        except subprocess.CalledProcessError as e:
            raise CommandError('La copia no se puede leer: ' + e.stderr.decode(errors='replace')[-800:])
        lineas = [linea for linea in salida.splitlines() if ' TABLE DATA ' in linea]
        faltan = [t for t in TABLAS_OBLIGATORIAS if not any(f' {t} ' in f'{linea} ' for linea in lineas)]
        if faltan:
            raise CommandError('A la copia le faltan tablas: ' + ', '.join(faltan))
        return len(lineas)

    def _sha256(self, ruta):
        h = hashlib.sha256()
        with open(ruta, 'rb') as f:
            for bloque in iter(lambda: f.read(1 << 20), b''):
                h.update(bloque)
        return h.hexdigest()

    def _r2(self):
        bucket = os.environ.get('R2_BUCKET_RESPALDOS', '').strip()
        if not bucket:
            raise CommandError('Falta R2_BUCKET_RESPALDOS. Tiene que ser un bucket privado, '
                               'distinto del de las fotos, que es público.')
        if bucket == os.environ.get('R2_BUCKET', '').strip():
            raise CommandError('R2_BUCKET_RESPALDOS no puede ser el mismo bucket de las fotos.')

        clave = os.environ.get('R2_RESPALDOS_ACCESS_KEY_ID') or os.environ.get('R2_ACCESS_KEY_ID')
        secreto = os.environ.get('R2_RESPALDOS_SECRET_ACCESS_KEY') or os.environ.get('R2_SECRET_ACCESS_KEY')
        endpoint = os.environ.get('R2_ENDPOINT_URL')
        if not (clave and secreto and endpoint):
            raise CommandError('Faltan las credenciales de R2 (R2_ENDPOINT_URL y la clave de acceso).')

        import boto3
        cliente = boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=clave,
                               aws_secret_access_key=secreto, region_name='auto')
        return cliente, bucket

    def _rotar(self, cliente, bucket, conservar):
        if conservar < 1:
            return 0
        objetos = []
        paginador = cliente.get_paginator('list_objects_v2')
        for pagina in paginador.paginate(Bucket=bucket, Prefix=PREFIJO):
            objetos.extend(pagina.get('Contents', []))
        objetos.sort(key=lambda o: o['LastModified'], reverse=True)
        sobrantes = objetos[conservar:]
        for o in sobrantes:
            cliente.delete_object(Bucket=bucket, Key=o['Key'])
        return len(sobrantes)
