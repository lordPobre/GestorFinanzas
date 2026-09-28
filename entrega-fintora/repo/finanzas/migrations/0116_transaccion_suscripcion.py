import django.db.models.deletion
from django.db import migrations, models


def vincular(apps, schema_editor):
    Suscripcion = apps.get_model('finanzas', 'Suscripcion')
    Transaccion = apps.get_model('finanzas', 'Transaccion')
    for sub in Suscripcion.objects.all().iterator():
        Transaccion.objects.filter(
            usuario_id=sub.usuario_id, tipo='EGRESO', es_cuota=False,
            descripcion=f'Suscripción: {sub.nombre}', suscripcion__isnull=True,
        ).update(suscripcion=sub)


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0115_eventoseguridad'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaccion',
            name='suscripcion',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='cobros', to='finanzas.suscripcion'),
        ),
        migrations.RunPython(vincular, migrations.RunPython.noop),
    ]
