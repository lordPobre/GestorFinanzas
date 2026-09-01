"""Verificación en dos pasos.

Requiere:  pip install pyotp

Cambia dependencies por tu última migración y corre migrate.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        # ↓ CAMBIA ESTO por tu última migración
        ('finanzas', '0105_perfil_foto'),
    ]

    operations = [
        migrations.CreateModel(
            name='SegundoFactor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('secreto', models.CharField(max_length=64)),
                ('activo', models.BooleanField(default=False)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('ultimo_uso', models.DateTimeField(blank=True, null=True)),
                ('ultimo_codigo', models.CharField(blank=True, max_length=6)),
                ('usuario', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='segundo_factor', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Segundo factor',
                     'verbose_name_plural': 'Segundos factores'},
        ),
        migrations.CreateModel(
            name='CodigoRespaldo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('codigo_hash', models.CharField(max_length=128)),
                ('usado', models.BooleanField(default=False)),
                ('usado_en', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='codigos_respaldo', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Código de respaldo',
                     'verbose_name_plural': 'Códigos de respaldo'},
        ),
    ]
