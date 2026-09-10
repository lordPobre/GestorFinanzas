"""Aviso mensual por correo: preferencia, día y registro del último envío.

Encendido por defecto (aviso_mensual=True) también para las cuentas que ya
existen: es un recordatorio de lo que uno mismo anotó, y quien no lo quiera
lo apaga en su perfil.

aviso_ultimo_periodo guarda el mes del último envío (año*100+mes). Sin él,
una tarea que corra dos veces el día 20 manda el correo dos veces.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0109_userprofile_google_sub'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='aviso_mensual',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='aviso_dia',
            field=models.IntegerField(default=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='aviso_ultimo_periodo',
            field=models.IntegerField(default=0),
        ),
    ]
