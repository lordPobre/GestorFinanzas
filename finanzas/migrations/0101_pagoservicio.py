"""Registro de pagos mensuales de suscripciones.

Cambia 'dependencies' por tu migración anterior (normalmente
0100_pagocuota) y corre:

    python manage.py migrate
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        # ↓ CAMBIA ESTO si tu migración anterior se llama distinto
        ('finanzas', '0100_pagocuota'),
    ]

    operations = [
        migrations.CreateModel(
            name='PagoServicio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('periodo', models.IntegerField(db_index=True,
                                                help_text='Mes al que corresponde: año*100+mes')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('fecha_pago', models.DateField(default=django.utils.timezone.now)),
                ('suscripcion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                  related_name='pagos',
                                                  to='finanzas.suscripcion')),
            ],
            options={'ordering': ['-periodo']},
        ),
        migrations.AddConstraint(
            model_name='pagoservicio',
            constraint=models.UniqueConstraint(fields=('suscripcion', 'periodo'),
                                               name='pago_servicio_unico_por_mes'),
        ),
    ]
