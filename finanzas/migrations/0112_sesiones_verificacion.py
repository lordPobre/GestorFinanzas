from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def marcar_verificados(apps, schema_editor):
    """Las cuentas que ya existen quedan verificadas.

    No se puede exigir a alguien que lleva meses usando la app que confirme
    un correo que nunca se le pidió: el resultado sería un aviso permanente
    en el perfil de todos el día del despliegue. El doble opt-in aplica
    desde acá en adelante, a las altas nuevas.
    """
    UserProfile = apps.get_model('finanzas', 'UserProfile')
    UserProfile.objects.all().update(correo_verificado=True)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0111_privacidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='correo_verificado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='correo_verificado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(marcar_verificados, migrations.RunPython.noop),
        migrations.CreateModel(
            name='SesionActiva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('clave', models.CharField(db_index=True, max_length=40, unique=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('agente', models.CharField(blank=True, max_length=300)),
                ('creada', models.DateTimeField(default=django.utils.timezone.now)),
                ('ultima_vez', models.DateTimeField(default=django.utils.timezone.now)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='sesiones',
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Sesión activa',
                'verbose_name_plural': 'Sesiones activas',
                'ordering': ['-ultima_vez'],
            },
        ),
    ]
