"""Categorías propias del usuario.

Crea el modelo Categoria. No toca Transaccion.categoria: sigue siendo un
CharField, y Django solo valida `choices` en los formularios, así que un
slug propio se guarda sin problema.

Cambia 'dependencies' por tu migración anterior y corre:

    python manage.py migrate
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        # ↓ CAMBIA ESTO por tu migración anterior
        ('finanzas', '0103_categorias_cuotas'),
    ]

    operations = [
        migrations.CreateModel(
            name='Categoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=40)),
                ('slug', models.SlugField(max_length=50)),
                ('tipo', models.CharField(
                    choices=[('EGRESO', 'Gasto'), ('INGRESO', 'Ingreso')],
                    default='EGRESO', max_length=10)),
                ('color', models.CharField(default='#ffaa2c', max_length=20)),
                ('icono', models.CharField(default='fa-tag', max_length=30)),
                ('activa', models.BooleanField(default=True)),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='categorias', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['tipo', 'nombre']},
        ),
        migrations.AddConstraint(
            model_name='categoria',
            constraint=models.UniqueConstraint(
                fields=('usuario', 'slug'), name='categoria_unica_por_usuario'),
        ),
    ]
