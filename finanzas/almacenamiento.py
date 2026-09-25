import os

from django.core.files.storage import default_storage
from django.utils.functional import LazyObject

SEGUNDOS_URL_FIRMADA = 6 * 60 * 60


def r2_configurado():
    return all(os.environ.get(k) for k in (
        'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY',
        'R2_BUCKET', 'R2_ENDPOINT_URL',
    ))


class AlmacenMedia(LazyObject):

    def _setup(self):
        if not r2_configurado():
            self._wrapped = default_storage
            return

        from storages.backends.s3 import S3Storage

        self._wrapped = S3Storage(
            access_key=os.environ['R2_ACCESS_KEY_ID'],
            secret_key=os.environ['R2_SECRET_ACCESS_KEY'],
            bucket_name=os.environ['R2_BUCKET'],
            endpoint_url=os.environ['R2_ENDPOINT_URL'],
            region_name='auto',
            signature_version='s3v4',
            querystring_auth=True,
            querystring_expire=SEGUNDOS_URL_FIRMADA,
            custom_domain=None,
            file_overwrite=False,
            default_acl=None,
            object_parameters={'CacheControl': f'private, max-age={SEGUNDOS_URL_FIRMADA}'},
        )


almacen_media = AlmacenMedia()


def obtener_almacen():
    return almacen_media
