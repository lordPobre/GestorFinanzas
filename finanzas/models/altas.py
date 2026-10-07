from django.db import models
from django.utils import timezone


class AltaPendiente(models.Model):
    correo = models.EmailField(db_index=True)
    username = models.CharField(max_length=150)
    password = models.CharField(max_length=128)
    nombre_completo = models.CharField(max_length=100, blank=True)
    politica_version = models.CharField(max_length=20)
    token = models.CharField(max_length=64, unique=True)
    creada = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Registro sin confirmar'
        verbose_name_plural = 'Registros sin confirmar'

    def __str__(self):
        return f'Registro sin confirmar de {self.username}'
