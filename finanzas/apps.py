"""Configuración de la app.

Existe por una sola razón: conectar las señales de sesión al arrancar. Sin
un ready() donde importar finanzas.sesiones, los receptores de
user_logged_in y user_logged_out no se registran nunca y la pantalla de
sesiones abiertas queda vacía para todos.
"""
from importlib import import_module

from django.apps import AppConfig


class FinanzasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finanzas'

    def ready(self):
        for modulo in ('sesiones', 'auditoria', 'servicios.senales'):
            import_module(f'{self.name}.{modulo}')
