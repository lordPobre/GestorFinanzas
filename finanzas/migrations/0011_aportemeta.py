from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0010_transaccion_es_cuota'),
    ]

    operations = [
        migrations.CreateModel(
            name='AporteMeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=12)),
                ('fecha', models.DateField(default=django.utils.timezone.now)),
                ('nota', models.CharField(blank=True, max_length=120)),
                ('meta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aportes', to='finanzas.metaahorro')),
            ],
            options={'ordering': ['-fecha', '-id']},
        ),
    ]
