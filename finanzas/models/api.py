from django.contrib.auth.models import User
from django.db import models


class ClaveApi(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='clave_api')
    huella = models.CharField(max_length=64, unique=True)
    prefijo = models.CharField(max_length=12)
    creada = models.DateTimeField(auto_now_add=True)
    usada = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.usuario} · {self.prefijo}…'
