from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0129_transaccion_origen_datos'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='transaccion',
            constraint=models.UniqueConstraint(
                condition=models.Q(('periodo_cobro__isnull', False), ('suscripcion__isnull', False)),
                fields=('suscripcion', 'periodo_cobro'),
                name='cobro_suscripcion_unico_por_mes'),
        ),
    ]
