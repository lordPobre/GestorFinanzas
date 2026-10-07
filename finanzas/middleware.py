import logging
import os
import secrets
import time
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers

from . import marketing

log = logging.getLogger('finanzas')


def _origenes_imagenes():
    origenes = ["'self'", 'data:', 'blob:']
    host = urlparse(os.environ.get('R2_ENDPOINT_URL', '').strip()).netloc
    if host:
        origenes += [f'https://{host}', f'https://*.{host}']
    extra = os.environ.get('CSP_IMG_EXTRA', '').split()
    origenes += [o for o in extra if o.startswith('https://')]
    return ' '.join(origenes)


IMG_SRC = _origenes_imagenes()


class Redireccion308(HttpResponsePermanentRedirect):
    status_code = 308


class DominioCanonicoMiddleware:

    EXENTAS = ('/salud/',)
    HOSTS_INTERNOS = ('healthcheck.railway.app',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonico = getattr(settings, 'DOMINIO_CANONICO', '')
        if canonico and not settings.DEBUG and request.path not in self.EXENTAS:
            host = (request.META.get('HTTP_X_FORWARDED_HOST') if settings.USE_X_FORWARDED_HOST
                    else '') or request.META.get('HTTP_HOST', '')
            host = host.split(',')[0].strip().split(':')[0].lower()
            interno = host in self.HOSTS_INTERNOS or host.endswith('.railway.internal')
            if host != canonico and not interno:
                destino = f'https://{canonico}{request.get_full_path()}'
                clase = (HttpResponsePermanentRedirect if request.method in ('GET', 'HEAD')
                         else Redireccion308)
                return clase(destino)
        return self.get_response(request)


PIXELES_CON_ESTILOS = ('googletagmanager.com', 'google-analytics.com', 'facebook.net',
                       'tiktok.com', 'ads-twitter.com', 'twitter.com')

RUTAS_SIN_ESTILO_EN_LINEA = frozenset({
    'login', 'verificar_codigo', 'registro', 'confirmar_alta', 'verificar_correo',
    'recuperar', 'restablecer', 'privacidad', 'terminos', 'seguridad',
})


def _atributos_style(request, respuesta):
    nombre = getattr(getattr(request, 'resolver_match', None), 'url_name', None)
    if nombre in RUTAS_SIN_ESTILO_EN_LINEA and respuesta.status_code < 400:
        return "style-src-attr 'none'"
    return "style-src-attr 'unsafe-inline'"


class PoliticaContenidoMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)

        respuesta = self.get_response(request)

        es_html = 'text/html' in respuesta.get('Content-Type', '')
        if getattr(settings, 'ES_STAGING', False):
            respuesta['X-Robots-Tag'] = 'noindex, nofollow'
        elif es_html and not marketing.es_indexable(request):
            respuesta['X-Robots-Tag'] = 'noindex, nofollow'

        ruta_admin = getattr(settings, 'ADMIN_URL', '')
        if ruta_admin and request.path.startswith(f'/{ruta_admin}/'):
            return respuesta

        if not es_html:
            return respuesta

        extra = {'script': [], 'conectar': [], 'imagen': []}
        if marketing.es_publica(request) or getattr(request, 'marketing_evento', False):
            extra = marketing.origenes(marketing.config())

        def mas(clave):
            return ''.join(' ' + o for o in extra[clave])

        con_pixeles = any(p in o for o in extra['script'] for p in PIXELES_CON_ESTILOS)
        estilos = [] if con_pixeles or (settings.DEBUG and respuesta.status_code >= 400) else [
            f"style-src-elem 'self' 'nonce-{request.csp_nonce}'",
            _atributos_style(request, respuesta),
        ]

        respuesta['Content-Security-Policy'] = '; '.join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{request.csp_nonce}'{mas('script')}",
            "style-src 'self' 'unsafe-inline'",
            *estilos,
            "font-src 'self'",
            f"img-src {IMG_SRC}{mas('imagen')}",
            f"connect-src 'self'{mas('conectar')}",
            "media-src 'self' blob:",
            "frame-src 'none'",
            "object-src 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "upgrade-insecure-requests",
        ])
        respuesta['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        )
        return respuesta


def nonce_contexto(request):
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


class SinCacheMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        usuario = getattr(request, 'user', None)
        if (usuario is not None and usuario.is_authenticated
                and not respuesta.has_header('Cache-Control')):
            add_never_cache_headers(respuesta)
        return respuesta


class SesionAbsolutaMiddleware:

    CLAVE = 'inicio_sesion'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)
        if usuario is not None and usuario.is_authenticated:
            vencida = self._revisar(request, usuario)
            if vencida is not None:
                return vencida

        from . import aparatos
        respuesta = self.get_response(request)
        return aparatos.poner_cookie(request, respuesta, not settings.DEBUG)

    def _revisar(self, request, usuario):
        maximo = getattr(settings, 'SESION_MAXIMA_HORAS', 168) * 3600
        inicio = request.session.get(self.CLAVE)
        try:
            edad = time.time() - float(inicio) if inicio is not None else None
        except (TypeError, ValueError):
            edad = None
        if edad is None:
            request.session[self.CLAVE] = time.time()
            return None
        if edad <= maximo:
            return None

        from django.contrib import messages
        from django.contrib.auth import logout
        from django.contrib.auth.views import redirect_to_login

        from . import auditoria

        auditoria.registrar('sesion_vencida', request, usuario)
        logout(request)
        dias = max(1, round(maximo / 86400))
        texto = (f'Por seguridad, la sesión se cierra cada {dias} día'
                 f'{"s" if dias != 1 else ""}. Vuelve a entrar.')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'msg': texto}, status=401)
        messages.info(request, texto)
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)


class ActividadMiddleware:

    CLAVE = 'actividad_dia'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)
        if usuario is not None and usuario.is_authenticated:
            self._marcar_dia(request, usuario)
            self._marcar_sesion(request)

        return self.get_response(request)

    def _marcar_dia(self, request, usuario):
        hoy = timezone.localdate().isoformat()
        if request.session.get(self.CLAVE) == hoy:
            return

        from .models import UserProfile

        try:
            ahora = timezone.now()
            filas = UserProfile.objects.filter(usuario=usuario).update(ultima_actividad=ahora)
            if not filas:
                UserProfile.objects.get_or_create(
                    usuario=usuario, defaults={'ultima_actividad': ahora})
            request.session[self.CLAVE] = hoy
        except Exception:
            log.warning('No se pudo anotar la actividad del usuario %s',
                        getattr(usuario, 'pk', '?'), exc_info=True)

    def _marcar_sesion(self, request):
        from . import sesiones

        try:
            sesiones.tocar(request)
        except Exception:
            log.warning('No se pudo refrescar la sesión abierta', exc_info=True)
