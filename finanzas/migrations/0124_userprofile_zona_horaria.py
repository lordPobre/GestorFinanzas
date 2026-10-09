from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0123_altapendiente'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='zona_horaria',
            field=models.CharField(default='America/Santiago', max_length=64),
        ),
    ]
