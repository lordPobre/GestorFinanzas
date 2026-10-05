import logging
import os
import secrets
from urllib.parse import urlparse

from django.conf import settings
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

        respuesta['Content-Security-Policy'] = '; '.join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{request.csp_nonce}'{mas('script')}",
            "style-src 'self' 'unsafe-inline'",
            "font-src 'self'",
            f"img-src {IMG_SRC}{mas('imagen')}",
            f"connect-src 'self'{mas('conectar')}",
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
