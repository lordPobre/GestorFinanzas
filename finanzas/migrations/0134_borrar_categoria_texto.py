from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0133_categoria_ref_obligatoria'),
    ]

    operations = [
        migrations.RemoveConstraint(model_name='topecategoria', name='tope_unico_por_categoria'),
        migrations.RemoveField(model_name='transaccion', name='categoria'),
        migrations.RemoveField(model_name='topecategoria', name='categoria'),
        migrations.RemoveField(model_name='gastopendiente', name='categoria'),
        migrations.RemoveField(model_name='suscripcion', name='categoria'),
        migrations.RemoveField(model_name='deuda', name='categoria'),
        migrations.AlterModelOptions(name='topecategoria', options={'ordering': ['categoria_ref__nombre']}),
        migrations.AddConstraint(
            model_name='topecategoria',
            constraint=models.UniqueConstraint(fields=('usuario', 'categoria_ref'),
                                               name='tope_unico_por_categoria'),
        ),
    ]
