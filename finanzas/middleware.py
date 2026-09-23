"""Middleware de seguridad propio.

Sin django-csp: la política de esta app es corta y fija, y una dependencia
más es una superficie más que mantener y actualizar.
"""
import logging
import secrets

log = logging.getLogger("finanzas")

class PoliticaContenidoMiddleware:
    """Content-Security-Policy: la última barrera contra el XSS.

    Si algún día se cuela una inyección —por un descuido, por una
    dependencia—, el navegador se niega a ejecutar el script porque no
    viene de un origen permitido. Es defensa en profundidad: no sustituye a
    escapar la salida, la respalda.

    Las fuentes salen de lo que la app carga de verdad:
      - Chart.js desde jsdelivr
      - Font Awesome desde cdnjs
      - Manrope y JetBrains Mono desde Google Fonts
      - Las fotos de perfil desde R2

    Si agregas otro CDN y no lo pones aquí, el navegador lo bloquea y el
    recurso no carga. Es el precio de la protección, y es preferible a una
    política tan abierta que no proteja nada.
    """

    CDN_SCRIPTS = "https://cdn.jsdelivr.net"
    CDN_ESTILOS = "https://cdnjs.cloudflare.com https://fonts.googleapis.com"
    CDN_FUENTES = "https://fonts.gstatic.com https://cdnjs.cloudflare.com"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)

        respuesta = self.get_response(request)

        # El entorno de pruebas no se indexa. Sin esto, un staging con
        # dominio público termina en Google compitiendo con el real.
        try:
            from django.conf import settings
            if getattr(settings, 'ES_STAGING', False):
                respuesta["X-Robots-Tag"] = "noindex, nofollow"
        except Exception:
            pass

        from django.conf import settings as _ajustes
        ruta_admin = getattr(_ajustes, 'ADMIN_URL', '')
        if ruta_admin and request.path.startswith(f"/{ruta_admin}/"):
            return respuesta

        tipo = respuesta.get("Content-Type", "")
        if "text/html" not in tipo:
            return respuesta

        img = "'self' data: blob: https:"

        politica = "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{request.csp_nonce}' {self.CDN_SCRIPTS}",
            f"style-src 'self' 'unsafe-inline' {self.CDN_ESTILOS}",
            f"font-src 'self' {self.CDN_FUENTES}",
            f"img-src {img}",
            "connect-src 'self'",
            "frame-src 'none'",
            "object-src 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
        ])

        respuesta["Content-Security-Policy"] = politica

        respuesta["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        return respuesta

def nonce_contexto(request):
    """Context processor: deja el nonce a mano en las plantillas."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}

class ActividadMiddleware:
    """Anota una vez al día que la cuenta se usó.

    Hace falta para el borrado por inactividad, y `User.last_login` no
    sirve: quien deja la sesión abierta no vuelve a pasar por `login()`, así
    que su `last_login` queda congelado y una cuenta de uso diario parecería
    abandonada.

    Una escritura por petición sería un UPDATE por cada carga de pantalla.
    La marca del día vive en la sesión, que ya está cargada, así que el
    coste real es una escritura al día por usuario.

    Va en la fase de PETICIÓN, antes de la vista. En la de respuesta la
    escritura comparte transacción con todo lo que la vista haya hecho: si
    algo de ahí la dejó en mal estado, esta anotación falla en silencio y el
    plazo de conservación declarado deja de cumplirse sin que nadie lo note.
    Por lo mismo el fallo se registra en vez de pasarse por alto.
    """

    CLAVE = "actividad_dia"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated:
            self._marcar_dia(request, usuario)
            self._marcar_sesion(request)

        return self.get_response(request)

    def _marcar_dia(self, request, usuario):
        from django.utils import timezone

        hoy = timezone.localdate().isoformat()
        if request.session.get(self.CLAVE) == hoy:
            return

        try:
            from .models import UserProfile
            filas = UserProfile.objects.filter(usuario=usuario).update(
                ultima_actividad=timezone.now())
            if not filas:
                # Cuenta sin perfil: pasa con las creadas antes de que
                # existiera el modelo, y sin fila no hay dónde anotar nada.
                UserProfile.objects.get_or_create(
                    usuario=usuario, defaults={'ultima_actividad': timezone.now()})
            request.session[self.CLAVE] = hoy
        except Exception:
            log.warning('No se pudo anotar la actividad del usuario %s',
                        getattr(usuario, 'pk', '?'), exc_info=True)

    def _marcar_sesion(self, request):
        """El «visto por última vez» de la pantalla de sesiones.

        Tiene su propio intervalo porque un dato de granularidad diaria no
        sirve para reconocer una sesión ajena recién abierta. Y va aparte
        para que un error acá —dos peticiones simultáneas creando la misma
        fila, por ejemplo— no arrastre a la anotación de actividad.
        """
        try:
            from . import sesiones
            sesiones.tocar(request)
        except Exception:
            log.warning('No se pudo refrescar la sesión abierta', exc_info=True)
