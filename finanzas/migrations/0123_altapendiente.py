import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0122_userprofile_politica_avisada'),
    ]

    operations = [
        migrations.CreateModel(
            name='AltaPendiente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('correo', models.EmailField(db_index=True, max_length=254)),
                ('username', models.CharField(max_length=150)),
                ('password', models.CharField(max_length=128)),
                ('nombre_completo', models.CharField(blank=True, max_length=100)),
                ('politica_version', models.CharField(max_length=20)),
                ('token', models.CharField(max_length=64, unique=True)),
                ('creada', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Registro sin confirmar',
                'verbose_name_plural': 'Registros sin confirmar',
            },
        ),
    ]
