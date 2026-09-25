import logging
import secrets

from django.conf import settings
from django.utils import timezone

log = logging.getLogger('finanzas')


class PoliticaContenidoMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)

        respuesta = self.get_response(request)

        if getattr(settings, 'ES_STAGING', False):
            respuesta['X-Robots-Tag'] = 'noindex, nofollow'

        ruta_admin = getattr(settings, 'ADMIN_URL', '')
        if ruta_admin and request.path.startswith(f'/{ruta_admin}/'):
            return respuesta

        if 'text/html' not in respuesta.get('Content-Type', ''):
            return respuesta

        respuesta['Content-Security-Policy'] = '; '.join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{request.csp_nonce}'",
            "style-src 'self' 'unsafe-inline'",
            "font-src 'self'",
            "img-src 'self' data: blob: https:",
            "connect-src 'self'",
            "frame-src 'none'",
            "object-src 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
        ])
        respuesta['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        )
        return respuesta


def nonce_contexto(request):
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


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
