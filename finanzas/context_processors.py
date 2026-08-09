"""
Context processor que inyecta la moneda del usuario en todos los templates.
Así {{ simbolo_moneda }} y {{ codigo_moneda }} están disponibles globalmente.
"""

# Símbolo y locale por cada moneda soportada
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
    """Devuelve el símbolo y config de moneda según el perfil del usuario."""
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
