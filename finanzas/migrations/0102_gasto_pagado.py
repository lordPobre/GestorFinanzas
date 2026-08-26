"""Estado de pago en los gastos únicos.

Agrega Transaccion.pagado y Transaccion.fecha_pago.

pagado usa default=True a propósito: todo lo que ya está en la base se
anotó después de pagarlo, así que darlo por pagado es lo correcto. Los
gastos nuevos pueden nacer sin pagar desde el panel de registro.

Cambia 'dependencies' por tu migración anterior y corre:

    python manage.py migrate
"""
from django.db import migrations, models


def marcar_pagados(apps, schema_editor):
    """Rellena fecha_pago con la fecha del gasto en lo que ya existe.

    Sin esto los gastos viejos dirían solo 'Pagado', sin cuándo. La fecha
    del gasto es la mejor aproximación disponible: es el día en que se
    anotó, que en la práctica era el día en que se pagó.
    """
    Transaccion = apps.get_model('finanzas', 'Transaccion')
    Transaccion.objects.filter(
        tipo='EGRESO', es_cuota=False, fecha_pago__isnull=True,
    ).update(fecha_pago=models.F('fecha'))


def limpiar(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        # ↓ CAMBIA ESTO por tu migración anterior
        ('finanzas', '0101_pagoservicio'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaccion',
            name='pagado',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='transaccion',
            name='fecha_pago',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(marcar_pagados, limpiar),
    ]
