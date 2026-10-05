from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0118_sugerenciadescartada'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clave', models.CharField(max_length=200, unique=True)),
                ('cuenta', models.PositiveIntegerField(default=0)),
                ('vence', models.DateTimeField(db_index=True)),
            ],
            options={
                'verbose_name': 'Contador de intentos',
                'verbose_name_plural': 'Contadores de intentos',
            },
        ),
        migrations.CreateModel(
            name='DispositivoConocido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('huella', models.CharField(max_length=64)),
                ('agente', models.CharField(blank=True, max_length=300)),
                ('creado', models.DateTimeField(default=django.utils.timezone.now)),
                ('ultima_vez', models.DateTimeField(default=django.utils.timezone.now)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dispositivos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Aparato conocido',
                'verbose_name_plural': 'Aparatos conocidos',
                'ordering': ['-ultima_vez'],
            },
        ),
        migrations.AddConstraint(
            model_name='dispositivoconocido',
            constraint=models.UniqueConstraint(fields=('usuario', 'huella'), name='dispositivo_unico'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='email_pendiente',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='email_pendiente_desde',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='eventoseguridad',
            name='tipo',
            field=models.CharField(choices=[('acceso', 'Acceso'), ('acceso_fallido', 'Acceso fallido'), ('salida', 'Salida'), ('bloqueo', 'Bloqueo por intentos'), ('codigo_fallido', 'Código de verificación incorrecto'), ('2fa_activada', 'Verificación en dos pasos activada'), ('2fa_desactivada', 'Verificación en dos pasos desactivada'), ('codigos_regenerados', 'Códigos de respaldo regenerados'), ('codigo_respaldo_usado', 'Código de respaldo usado'), ('passkey_agregada', 'Face ID o huella vinculado'), ('passkey_quitada', 'Face ID o huella quitado'), ('passkey_fallida', 'Face ID o huella rechazado'), ('contrasena_cambiada', 'Contraseña cambiada'), ('recuperacion_pedida', 'Recuperación de contraseña pedida'), ('contrasena_restablecida', 'Contraseña restablecida'), ('sesiones_cerradas', 'Sesiones cerradas a distancia'), ('datos_descargados', 'Descarga de datos personales'), ('cuenta_eliminada', 'Cuenta eliminada'), ('admin_denegado', 'Acceso al panel denegado'), ('correo_cambio_pedido', 'Cambio de correo pedido'), ('correo_cambiado', 'Correo cambiado'), ('dispositivo_nuevo', 'Acceso desde un aparato nuevo'), ('sesion_vencida', 'Sesión vencida')], db_index=True, max_length=30),
        ),
    ]
