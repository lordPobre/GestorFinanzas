import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0114_passkey'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoSeguridad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creado', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('tipo', models.CharField(choices=[
                    ('acceso', 'Acceso'),
                    ('acceso_fallido', 'Acceso fallido'),
                    ('salida', 'Salida'),
                    ('bloqueo', 'Bloqueo por intentos'),
                    ('codigo_fallido', 'Código de verificación incorrecto'),
                    ('2fa_activada', 'Verificación en dos pasos activada'),
                    ('2fa_desactivada', 'Verificación en dos pasos desactivada'),
                    ('codigos_regenerados', 'Códigos de respaldo regenerados'),
                    ('codigo_respaldo_usado', 'Código de respaldo usado'),
                    ('passkey_agregada', 'Face ID o huella vinculado'),
                    ('passkey_quitada', 'Face ID o huella quitado'),
                    ('passkey_fallida', 'Face ID o huella rechazado'),
                    ('contrasena_cambiada', 'Contraseña cambiada'),
                    ('recuperacion_pedida', 'Recuperación de contraseña pedida'),
                    ('contrasena_restablecida', 'Contraseña restablecida'),
                    ('sesiones_cerradas', 'Sesiones cerradas a distancia'),
                    ('datos_descargados', 'Descarga de datos personales'),
                    ('cuenta_eliminada', 'Cuenta eliminada'),
                    ('admin_denegado', 'Acceso al panel denegado'),
                ], db_index=True, max_length=30)),
                ('referencia', models.CharField(blank=True, db_index=True, max_length=150)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('agente', models.CharField(blank=True, max_length=300)),
                ('detalle', models.CharField(blank=True, max_length=300)),
                ('usuario', models.ForeignKey(blank=True, null=True,
                                              on_delete=django.db.models.deletion.SET_NULL,
                                              related_name='eventos_seguridad',
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Evento de seguridad',
                'verbose_name_plural': 'Eventos de seguridad',
                'ordering': ['-creado'],
            },
        ),
    ]
