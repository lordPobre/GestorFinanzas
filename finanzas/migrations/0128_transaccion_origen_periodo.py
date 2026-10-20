from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0127_categoria_vinculo_datos'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaccion',
            name='origen',
            field=models.CharField(
                choices=[('manual', 'Anotado a mano'), ('suscripcion', 'Cobro de suscripción'),
                         ('pendiente', 'Cuenta por pagar'), ('cuota', 'Pago de cuota'),
                         ('cartola', 'Cartola')],
                default='manual', editable=False, max_length=12),
        ),
        migrations.AddField(
            model_name='transaccion',
            name='periodo_cobro',
            field=models.IntegerField(blank=True, editable=False, null=True),
        ),
    ]
