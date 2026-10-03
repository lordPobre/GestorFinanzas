import os
from urllib.parse import urlparse

SITIO = 'https://fintora.cl'
RUTAS_PUBLICAS = ('/', '/privacidad/', '/terminos/', '/seguridad/')
RUTAS_INDEXABLES = RUTAS_PUBLICAS + ('/login/', '/registro/')
PLAUSIBLE_SCRIPT = 'https://plausible.io/js/script.js'
CLAVE_EVENTO = 'marketing_registro'


def _env(nombre):
    return os.environ.get(nombre, '').strip()


def config():
    return {
        'ga4': _env('GA4_ID'),
        'meta': _env('META_PIXEL_ID'),
        'tiktok': _env('TIKTOK_PIXEL_ID'),
        'x': _env('X_PIXEL_ID'),
        'x_registro': _env('X_EVENTO_REGISTRO'),
        'plausible': _env('PLAUSIBLE_DOMINIO'),
        'plausible_src': _env('PLAUSIBLE_SCRIPT') or PLAUSIBLE_SCRIPT,
        'google_verificacion': _env('GOOGLE_SITE_VERIFICATION'),
    }


def hay_pixeles(c):
    return bool(c['ga4'] or c['meta'] or c['tiktok'] or c['x'])


def marcar_registro(request):
    request.session[CLAVE_EVENTO] = True


def tomar_evento(request):
    if request is None or not hasattr(request, 'session'):
        return False
    return bool(request.session.pop(CLAVE_EVENTO, False))


def _con_sesion(request):
    usuario = getattr(request, 'user', None)
    return bool(usuario is not None and usuario.is_authenticated)


def es_publica(request):
    if request.path not in RUTAS_PUBLICAS:
        return False
    return not (request.path == '/' and _con_sesion(request))


def es_indexable(request):
    if request.path not in RUTAS_INDEXABLES:
        return False
    return not (request.path == '/' and _con_sesion(request))


def origenes(c):
    script, conectar, imagen = [], [], []
    if c['plausible']:
        host = urlparse(c['plausible_src']).netloc
        if host:
            script.append(f'https://{host}')
            conectar.append(f'https://{host}')
    if c['ga4']:
        script.append('https://www.googletagmanager.com')
        conectar += ['https://*.google-analytics.com', 'https://*.analytics.google.com',
                     'https://www.googletagmanager.com']
        imagen += ['https://*.google-analytics.com', 'https://www.googletagmanager.com']
    if c['meta']:
        script.append('https://connect.facebook.net')
        conectar += ['https://www.facebook.com', 'https://connect.facebook.net']
        imagen.append('https://www.facebook.com')
    if c['tiktok']:
        script.append('https://analytics.tiktok.com')
        conectar.append('https://analytics.tiktok.com')
        imagen.append('https://analytics.tiktok.com')
    if c['x']:
        script.append('https://static.ads-twitter.com')
        conectar += ['https://static.ads-twitter.com', 'https://ads-twitter.com',
                     'https://ads-api.twitter.com', 'https://analytics.twitter.com']
        imagen += ['https://t.co', 'https://analytics.twitter.com']
    return {'script': script, 'conectar': conectar, 'imagen': imagen}
