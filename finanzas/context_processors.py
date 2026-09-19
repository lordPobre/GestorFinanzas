"""
Context processor que inyecta la moneda del usuario en todos los templates.
Así {{ simbolo_moneda }} y {{ codigo_moneda }} están disponibles globalmente.
"""

CONFIG_MONEDA = {
    'CLP': {'simbolo': '$',    'codigo': 'CLP', 'decimales': 0},
    'USD': {'simbolo': 'US$',  'codigo': 'USD', 'decimales': 2},
    'EUR': {'simbolo': '€',    'codigo': 'EUR', 'decimales': 2},
    'ARS': {'simbolo': '$',    'codigo': 'ARS', 'decimales': 2},
    'MXN': {'simbolo': '$',    'codigo': 'MXN', 'decimales': 2},
    'COP': {'simbolo': '$',    'codigo': 'COP', 'decimales': 0},
    'PEN': {'simbolo': 'S/',   'codigo': 'PEN', 'decimales': 2},
    'BRL': {'simbolo': 'R$',   'codigo': 'BRL', 'decimales': 2},
}

DEFAULT = CONFIG_MONEDA['CLP']


def moneda_usuario(request):
    if not request.user.is_authenticated:
        return {'simbolo_moneda': '$', 'codigo_moneda': 'CLP', 'decimales_moneda': 0}

    try:
        moneda = request.user.profile.moneda
    except Exception:
        moneda = 'CLP'

    cfg = CONFIG_MONEDA.get(moneda, DEFAULT)
    return {
        'simbolo_moneda': cfg['simbolo'],
        'codigo_moneda': cfg['codigo'],
        'decimales_moneda': cfg['decimales'],
    }


def entorno(request):
    """Deja a la vista si esto es el entorno de pruebas.

    Sin una marca visible, un staging con la base copiada se confunde con el
    real: se anota un gasto de verdad en la copia, o peor, se prueba un
    borrado creyendo que es de prueba.
    """
    from django.conf import settings
    return {
        'es_staging': bool(getattr(settings, 'ES_STAGING', False)),
        'nombre_entorno': getattr(settings, 'ENTORNO', 'produccion'),
    }
