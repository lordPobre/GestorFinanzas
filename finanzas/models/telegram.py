from django.contrib.auth.models import User
from django.db import models


class ChatTelegram(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_telegram')
    chat_id = models.BigIntegerField(unique=True)
    nombre = models.CharField(max_length=80, blank=True)
    conectado = models.DateTimeField(auto_now_add=True)
    usado = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.usuario} · Telegram'
