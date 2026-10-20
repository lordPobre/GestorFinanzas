from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0130_cobro_suscripcion_unico'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaccion',
            name='categoria',
            field=models.CharField(default='Otros', max_length=50),
        ),
        migrations.AlterField(
            model_name='deuda',
            name='categoria',
            field=models.CharField(default='Tecnologia', max_length=50),
        ),
    ]
