import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0120_userprofile_esfera_estado_visto'),
    ]

    operations = [
        migrations.AddField(
            model_name='persona',
            name='lado',
            field=models.CharField(choices=[('ME_DEBE', 'Me debe'), ('LE_DEBO', 'Le debo')],
                                   db_index=True, default='ME_DEBE', max_length=8),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='push_vence',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='push_dia_antes',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='push_topes',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='push_resumen',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='push_montos',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='push_ultimo_dia',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='TopeCategoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categoria', models.CharField(max_length=50)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('avisar', models.BooleanField(default=True)),
                ('aviso_periodo', models.IntegerField(default=0)),
                ('aviso_nivel', models.IntegerField(default=0)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='topes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['categoria'],
            },
        ),
        migrations.AddConstraint(
            model_name='topecategoria',
            constraint=models.UniqueConstraint(fields=('usuario', 'categoria'),
                                               name='tope_unico_por_categoria'),
        ),
        migrations.CreateModel(
            name='SuscripcionPush',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(max_length=500, unique=True)),
                ('p256dh', models.CharField(max_length=120)),
                ('auth', models.CharField(max_length=40)),
                ('agente', models.CharField(blank=True, max_length=200)),
                ('creada', models.DateTimeField(default=django.utils.timezone.now)),
                ('ultima_vez', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='suscripciones_push', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Aparato con recordatorios',
                'verbose_name_plural': 'Aparatos con recordatorios',
                'ordering': ['-creada'],
            },
        ),
    ]
