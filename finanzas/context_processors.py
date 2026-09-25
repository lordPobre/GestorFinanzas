from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

CONFIG_MONEDA = {
    'CLP': {'simbolo': '$', 'codigo': 'CLP', 'decimales': 0},
    'USD': {'simbolo': 'US$', 'codigo': 'USD', 'decimales': 2},
    'EUR': {'simbolo': '€', 'codigo': 'EUR', 'decimales': 2},
    'ARS': {'simbolo': '$', 'codigo': 'ARS', 'decimales': 2},
    'MXN': {'simbolo': '$', 'codigo': 'MXN', 'decimales': 2},
    'COP': {'simbolo': '$', 'codigo': 'COP', 'decimales': 0},
    'PEN': {'simbolo': 'S/', 'codigo': 'PEN', 'decimales': 2},
    'BRL': {'simbolo': 'R$', 'codigo': 'BRL', 'decimales': 2},
}

DEFAULT = CONFIG_MONEDA['CLP']


def moneda_usuario(request):
    moneda = 'CLP'
    if request.user.is_authenticated:
        try:
            moneda = request.user.profile.moneda
        except ObjectDoesNotExist:
            pass

    cfg = CONFIG_MONEDA.get(moneda, DEFAULT)
    return {
        'simbolo_moneda': cfg['simbolo'],
        'codigo_moneda': cfg['codigo'],
        'decimales_moneda': cfg['decimales'],
    }


def entorno(request):
    return {
        'es_staging': bool(getattr(settings, 'ES_STAGING', False)),
        'nombre_entorno': getattr(settings, 'ENTORNO', 'produccion'),
    }
