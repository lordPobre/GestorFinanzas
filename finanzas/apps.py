from importlib import import_module

from django.apps import AppConfig


class FinanzasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finanzas'

    def ready(self):
        for modulo in ('sesiones', 'auditoria', 'servicios.senales'):
            import_module(f'{self.name}.{modulo}')
