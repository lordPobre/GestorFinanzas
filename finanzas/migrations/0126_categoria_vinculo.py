from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _vinculo(related_name):
    return models.ForeignKey(
        blank=True, editable=False, null=True,
        on_delete=django.db.models.deletion.RESTRICT,
        related_name=related_name, to='finanzas.categoria')


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('finanzas', '0125_transaccion_indices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categoria',
            name='usuario',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='categorias', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddConstraint(
            model_name='categoria',
            constraint=models.UniqueConstraint(
                condition=models.Q(('usuario__isnull', True)),
                fields=('slug',), name='categoria_base_unica'),
        ),
        migrations.AddField(model_name='transaccion', name='categoria_ref', field=_vinculo('movimientos')),
        migrations.AddField(model_name='topecategoria', name='categoria_ref', field=_vinculo('topes')),
        migrations.AddField(model_name='gastopendiente', name='categoria_ref', field=_vinculo('gastos_pendientes')),
        migrations.AddField(model_name='suscripcion', name='categoria_ref', field=_vinculo('suscripciones')),
        migrations.AddField(model_name='deuda', name='categoria_ref', field=_vinculo('cuotas')),
    ]
