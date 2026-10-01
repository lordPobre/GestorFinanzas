from urllib.parse import urlsplit

from django import template
from django.urls import reverse

from .. import correo

register = template.Library()


@register.simple_tag(takes_context=True)
def url_sitio(context, nombre):
    ruta = reverse(nombre)
    enlace = context.get('enlace') or ''
    partes = urlsplit(str(enlace))
    if partes.scheme and partes.netloc:
        return f'{partes.scheme}://{partes.netloc}{ruta}'
    return correo.url_absoluta_sin_request(ruta)
