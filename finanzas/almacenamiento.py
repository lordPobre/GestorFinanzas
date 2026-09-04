"""Dónde se guardan los archivos que sube el usuario.

Hoy solo la foto de perfil, pero cualquier archivo futuro pasa por acá.

Dos modos, según haya credenciales de R2 en el entorno:

  · sin credenciales → disco local (MEDIA_ROOT). Es lo que quieres en
    desarrollo: no depende de la red ni gasta cuota.
  · con credenciales → Cloudflare R2.

Se elige solo, sin tocar código al desplegar. Un `if settings.DEBUG` no
serviría: en PythonAnywhere DEBUG es False y ahí puedes querer disco local
igual, mientras no tengas el bucket listo.
"""
import os

from django.core.files.storage import FileSystemStorage, default_storage
from django.utils.functional import LazyObject


def r2_configurado():
    """Hay credenciales suficientes para hablar con R2."""
    return all(os.environ.get(k) for k in (
        'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY',
        'R2_BUCKET', 'R2_ENDPOINT_URL',
    ))


class AlmacenMedia(LazyObject):
    """El almacén de los archivos del usuario.

    LazyObject y no una instancia directa: si se construyera al importar,
    Django evaluaría las credenciales antes de cargar settings y en un
    entorno sin R2 reventaría al arrancar en vez de caer al disco.
    """

    def _setup(self):
        if not r2_configurado():
            self._wrapped = default_storage
            return

        # La importación va dentro: django-storages solo hace falta cuando
        # R2 está configurado, así que en desarrollo no es una dependencia.
        from storages.backends.s3 import S3Storage

        # custom_domain espera SOLO el host. Si la variable trae el esquema,
        # django-storages le antepone el suyo y sale "https://https//host/…",
        # que no resuelve. Se limpia acá en vez de confiar en cómo se escribió
        # la variable de entorno.
        dominio = os.environ.get('R2_PUBLIC_DOMAIN', '').strip()
        for prefijo in ('https://', 'http://', '//'):
            if dominio.startswith(prefijo):
                dominio = dominio[len(prefijo):]
                break
        dominio = dominio.rstrip('/')

        self._wrapped = S3Storage(
            access_key=os.environ['R2_ACCESS_KEY_ID'],
            secret_key=os.environ['R2_SECRET_ACCESS_KEY'],
            bucket_name=os.environ['R2_BUCKET'],
            endpoint_url=os.environ['R2_ENDPOINT_URL'],
            region_name='auto',

            # Sin firmar la URL: con querystring_auth las direcciones caducan
            # y el avatar deja de cargar a los pocos minutos.
            querystring_auth=False,

            # El dominio público del bucket. Sin él las URL apuntan al
            # endpoint de la API, que no sirve imágenes al navegador.
            custom_domain=dominio or None,

            # No sobreescribir: dos usuarios que suban "foto.jpg" tendrían
            # el mismo nombre y uno pisaría al otro.
            file_overwrite=False,

            # Un año de caché. El nombre del archivo cambia al subir otra
            # foto, así que no hay riesgo de servir una vieja.
            object_parameters={'CacheControl': 'public, max-age=31536000'},
        )


almacen_media = AlmacenMedia()


def obtener_almacen():
    """El almacén, entregado como CALLABLE.

    Esto importa: cuando un ImageField recibe storage=<instancia>, Django
    serializa esa instancia dentro de la migración — con sus credenciales.
    En este proyecto eso ya pasó: la migración 0107 tiene la access_key y la
    secret_key de R2 escritas en texto plano dentro del repositorio.

    Con un callable, la migración guarda solo la referencia a esta función
    ('finanzas.almacenamiento.obtener_almacen') y nunca sus valores. Además
    deja de detectar cambios en el modelo cada vez que varía una variable de
    entorno, que es lo que hacía que makemigrations pidiera una migración
    nueva sin haber tocado nada.
    """
    return almacen_media
