"""Middleware de seguridad propio.

Sin django-csp: la política de esta app es corta y fija, y una dependencia
más es una superficie más que mantener y actualizar.
"""
import secrets


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
        # Un valor distinto por respuesta. Los <script> en línea de las
        # plantillas lo llevan; uno inyectado no puede adivinarlo.
        request.csp_nonce = secrets.token_urlsafe(16)

        respuesta = self.get_response(request)

        # El admin de Django usa estilos y scripts en línea sin nonce: con
        # la política puesta se rompe. Se deja fuera.
        if request.path.startswith("/admin"):
            return respuesta

        # Solo en respuestas HTML: en una imagen o un CSV la cabecera sobra.
        tipo = respuesta.get("Content-Type", "")
        if "text/html" not in tipo:
            return respuesta

        img = "'self' data: blob: https:"

        politica = "; ".join([
            "default-src 'self'",
            f"script-src 'self' 'nonce-{request.csp_nonce}' {self.CDN_SCRIPTS}",
            # unsafe-inline en estilos es inevitable: las plantillas usan
            # style="" en todas partes y el JS ajusta estilos en vivo. Un
            # estilo inyectado puede afear la página, no ejecutar código.
            f"style-src 'self' 'unsafe-inline' {self.CDN_ESTILOS}",
            f"font-src 'self' {self.CDN_FUENTES}",
            f"img-src {img}",
            # A dónde puede hablar la app: solo a sí misma.
            "connect-src 'self'",
            # Nada de <iframe>, <object> ni Flash.
            "frame-src 'none'",
            "object-src 'none'",
            # Los formularios solo envían al propio sitio: impide que una
            # inyección reescriba un action y mande los datos fuera.
            "form-action 'self'",
            # Nadie puede meter la app en un iframe (clickjacking).
            "frame-ancestors 'none'",
            "base-uri 'self'",
        ])

        respuesta["Content-Security-Policy"] = politica

        # Sin acceso a cámara, micrófono ni ubicación: la app no los usa, y
        # declararlo impide que un script inyectado los pida.
        respuesta["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        return respuesta


def nonce_contexto(request):
    """Context processor: deja el nonce a mano en las plantillas."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}
