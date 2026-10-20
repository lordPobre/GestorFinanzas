import django.db.models.deletion
from django.db import migrations, models


def _vinculo(related_name):
    return models.ForeignKey(blank=True, editable=False, on_delete=django.db.models.deletion.RESTRICT,
                             related_name=related_name, to='finanzas.categoria')


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0132_categoria_vinculo_completo'),
    ]

    operations = [
        migrations.AlterField(model_name='transaccion', name='categoria_ref', field=_vinculo('movimientos')),
        migrations.AlterField(model_name='topecategoria', name='categoria_ref', field=_vinculo('topes')),
        migrations.AlterField(model_name='gastopendiente', name='categoria_ref',
                              field=_vinculo('gastos_pendientes')),
        migrations.AlterField(model_name='suscripcion', name='categoria_ref', field=_vinculo('suscripciones')),
        migrations.AlterField(model_name='deuda', name='categoria_ref', field=_vinculo('cuotas')),
    ]
