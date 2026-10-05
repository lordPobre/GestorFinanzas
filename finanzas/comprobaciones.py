from django.conf import settings
from django.core.checks import Error, Warning, register


@register(deploy=True)
def defusedxml_instalado(app_configs, **kwargs):
    try:
        import defusedxml
    except ImportError:
        return [Error('Falta defusedxml: openpyxl leería los Excel subidos sin protección '
                      'contra XML malicioso.', hint='Instala requirements.txt.',
                      id='finanzas.E001')]
    del defusedxml
    return []


@register(deploy=True)
def dominio_canonico(app_configs, **kwargs):
    if settings.DEBUG or not getattr(settings, 'DOMINIO_CANONICO', ''):
        return []
    if settings.DOMINIO_CANONICO not in settings.ALLOWED_HOSTS:
        return [Warning(f'El dominio canónico {settings.DOMINIO_CANONICO} no está en ALLOWED_HOSTS.',
                        id='finanzas.W001')]
    return []
