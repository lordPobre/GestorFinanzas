"""Foto de perfil.

Requiere Pillow:  pip install Pillow

El almacenamiento se elige solo (finanzas/almacenamiento.py): Cloudflare R2
si hay credenciales en el entorno, disco local si no. Para el disco local
necesitas en settings.py:

    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

Y en el urls.py del proyecto, solo para desarrollo:

    from django.conf import settings
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

Cambia 'dependencies' por tu migración anterior y corre:

    python manage.py migrate

Nota sobre el campo: lleva storage= y upload_to= como callable. Django los
serializa en la migración, así que si más adelante cambias de almacén
generará una migración nueva sin datos — es solo metadatos, no toca los
archivos ya subidos.
"""
from django.db import migrations, models

import finanzas.models


class Migration(migrations.Migration):

    dependencies = [
        # ↓ CAMBIA ESTO por tu migración anterior
        ('finanzas', '0104_categoria'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='foto',
            field=models.ImageField(
                blank=True, null=True,
                upload_to=finanzas.models._ruta_avatar,
            ),
        ),
    ]
