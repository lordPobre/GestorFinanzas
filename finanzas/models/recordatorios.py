from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SuscripcionPush(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suscripciones_push')
    endpoint = models.CharField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=120)
    auth = models.CharField(max_length=40)
    agente = models.CharField(max_length=200, blank=True)
    creada = models.DateTimeField(default=timezone.now)
    ultima_vez = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creada']
        verbose_name = 'Aparato con recordatorios'
        verbose_name_plural = 'Aparatos con recordatorios'

    def __str__(self):
        return f'Recordatorios de {self.usuario.username}'
