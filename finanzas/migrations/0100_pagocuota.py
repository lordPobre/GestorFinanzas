"""Registro de pagos de cuotas por mes.

Crea PagoCuota y rellena el historial de las deudas que ya existen, para que
nada quede con el contador en un número y sin pagos que lo respalden.

IMPORTANTE: cambia la línea de 'dependencies' por el nombre de tu última
migración. Para saber cuál es:

    python manage.py showmigrations finanzas

Después:

    python manage.py migrate
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from dateutil.relativedelta import relativedelta


def poblar_pagos(apps, schema_editor):
    """Convierte el contador cuotas_pagadas en pagos con mes asignado.

    Se asume lo único razonable con la información que hay: si el contador
    dice 3, se pagaron los tres primeros meses del calendario. Es exactamente
    lo que el código viejo daba por supuesto, solo que ahora queda escrito
    en la base en vez de recalcularse cada vez.

    La transacción de cada pago se busca por descripción, que es como el
    código viejo las guardaba. Si no la encuentra, el pago se crea igual: el
    historial de cuotas importa más que el enlace al movimiento.
    """
    Deuda = apps.get_model('finanzas', 'Deuda')
    PagoCuota = apps.get_model('finanzas', 'PagoCuota')
    Transaccion = apps.get_model('finanzas', 'Transaccion')

    for deuda in Deuda.objects.all():
        pagadas = min(deuda.cuotas_pagadas or 0, deuda.cuotas_totales or 0)
        if pagadas <= 0:
            continue

        if deuda.cuotas_totales > 0:
            cuota = deuda.monto_total / deuda.cuotas_totales
        else:
            cuota = 0

        for i in range(pagadas):
            f = deuda.fecha_inicio + relativedelta(months=i)
            etiqueta = f'Cuota {i + 1}/{deuda.cuotas_totales} — {deuda.acreedor}'
            tx = Transaccion.objects.filter(
                usuario_id=deuda.usuario_id, es_cuota=True, descripcion=etiqueta,
            ).order_by('-fecha', '-id').first()

            PagoCuota.objects.create(
                deuda=deuda,
                periodo=f.year * 100 + f.month,
                monto=cuota,
                fecha_pago=tx.fecha if tx else f,
                transaccion=tx,
            )


def borrar_pagos(apps, schema_editor):
    """Marcha atrás: el contador cuotas_pagadas se mantiene, así que
    deshacer esta migración no pierde información."""
    apps.get_model('finanzas', 'PagoCuota').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        # ↓ CAMBIA ESTO por tu última migración de la app finanzas
        ('finanzas', '0016_alter_deuda_options_alter_transaccion_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='PagoCuota',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('periodo', models.IntegerField(db_index=True,
                                                help_text='Mes al que corresponde: año*100+mes')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('fecha_pago', models.DateField(default=django.utils.timezone.now,
                                                help_text='Cuándo se pagó de verdad')),
                ('deuda', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='pagos', to='finanzas.deuda')),
                ('transaccion', models.OneToOneField(blank=True, null=True,
                                                     on_delete=django.db.models.deletion.SET_NULL,
                                                     related_name='pago_cuota',
                                                     to='finanzas.transaccion')),
            ],
            options={'ordering': ['-periodo']},
        ),
        migrations.AddConstraint(
            model_name='pagocuota',
            constraint=models.UniqueConstraint(fields=('deuda', 'periodo'),
                                               name='pago_unico_por_mes'),
        ),
        migrations.RunPython(poblar_pagos, borrar_pagos),
    ]
