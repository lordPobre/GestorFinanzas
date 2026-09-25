from django.contrib.auth.models import User
from django.db import models


class RespuestaEncuesta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='respuestas_encuesta')
    creada = models.DateTimeField(auto_now_add=True, db_index=True)
    antiguedad = models.CharField(max_length=30, blank=True)
    frecuencia = models.CharField(max_length=30, blank=True)
    facilidad = models.PositiveSmallIntegerField()
    secciones = models.JSONField(default=list, blank=True)
    notas = models.JSONField(default=dict, blank=True)
    gusta = models.TextField(blank=True)
    molesta = models.TextField(blank=True)
    agregar = models.TextField(blank=True)
    sacar = models.TextField(blank=True)
    recomienda = models.PositiveSmallIntegerField()
    razon = models.TextField(blank=True)

    class Meta:
        ordering = ['-creada']

    def __str__(self):
        return f'Encuesta de {self.usuario.username} · {self.creada:%Y-%m-%d}'
