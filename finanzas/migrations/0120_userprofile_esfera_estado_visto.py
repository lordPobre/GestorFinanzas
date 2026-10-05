from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0119_seguridad_lote_b'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='esfera_estado_visto',
            field=models.CharField(blank=True, max_length=12),
        ),
    ]
