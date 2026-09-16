from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0110_aviso_mensual'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='analisis_ia',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='politica_version',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='politica_aceptada',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='ultima_actividad',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='aviso_inactividad_enviado',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
