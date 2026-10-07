from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0121_prestamos_topes_recordatorios'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='politica_avisada',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
