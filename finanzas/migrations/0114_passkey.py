import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0113_encuesta'),
    ]

    operations = [
        migrations.CreateModel(
            name='Passkey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('credencial_id', models.CharField(max_length=512, unique=True)),
                ('clave_publica', models.TextField()),
                ('contador', models.PositiveBigIntegerField(default=0)),
                ('nombre', models.CharField(max_length=60)),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('ultimo_uso', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='passkeys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Acceso con Face ID o huella',
                'verbose_name_plural': 'Accesos con Face ID o huella',
                'ordering': ['-creada'],
            },
        ),
    ]
