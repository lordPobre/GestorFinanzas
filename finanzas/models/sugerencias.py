from django.contrib.auth.models import User
from django.db import models


class SugerenciaDescartada(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sugerencias_descartadas')
    clave = models.CharField(max_length=80)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'clave'], name='sugerencia_descartada_unica'),
        ]

    def __str__(self):
        return f'{self.usuario_id}: {self.clave}'
