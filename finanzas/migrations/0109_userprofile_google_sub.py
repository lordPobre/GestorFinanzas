from django.db import migrations, models


class Migration(migrations.Migration):
    """Guarda el 'sub' de Google en el perfil.

    Es el identificador estable de la cuenta: no cambia aunque la persona
    cambie su correo de Gmail. Vincular solo por correo dejaría la cuenta
    colgando el día que alguien cambia de dirección.

    null=True y no blank a secas porque el campo es unique: en SQL varios
    NULL no chocan entre sí, pero varias cadenas vacías sí.
    """

    dependencies = [
        ('finanzas', '0108_alter_userprofile_foto'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='google_sub',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
