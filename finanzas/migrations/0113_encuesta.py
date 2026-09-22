import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0112_sesiones_verificacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='RespuestaEncuesta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creada', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('antiguedad', models.CharField(blank=True, max_length=30)),
                ('frecuencia', models.CharField(blank=True, max_length=30)),
                ('facilidad', models.PositiveSmallIntegerField()),
                ('secciones', models.JSONField(blank=True, default=list)),
                ('notas', models.JSONField(blank=True, default=dict)),
                ('gusta', models.TextField(blank=True)),
                ('molesta', models.TextField(blank=True)),
                ('agregar', models.TextField(blank=True)),
                ('sacar', models.TextField(blank=True)),
                ('recomienda', models.PositiveSmallIntegerField()),
                ('razon', models.TextField(blank=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='respuestas_encuesta', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-creada']},
        ),
    ]
