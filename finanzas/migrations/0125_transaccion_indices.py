from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0124_userprofile_zona_horaria'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='transaccion',
            index=models.Index(fields=['usuario', 'fecha'], name='trans_usuario_fecha'),
        ),
        migrations.AddIndex(
            model_name='transaccion',
            index=models.Index(fields=['usuario', 'tipo', 'fecha'], name='trans_usuario_tipo_fecha'),
        ),
    ]
