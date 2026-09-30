from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0117_reparar_cuotas_pagadas'),
    ]

    operations = [
        migrations.CreateModel(
            name='SugerenciaDescartada',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clave', models.CharField(max_length=80)),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sugerencias_descartadas', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='sugerenciadescartada',
            constraint=models.UniqueConstraint(fields=('usuario', 'clave'), name='sugerencia_descartada_unica'),
        ),
    ]
