from django import template
from django.core import signing

register = template.Library()

SAL = 'finanzas.voz'


def puede_usar(usuario):
    from ..voz import configurada
    if not (usuario and usuario.is_authenticated and configurada()):
        return False
    perfil = getattr(usuario, 'profile', None)
    return bool(perfil and perfil.analisis_ia)


@register.simple_tag(takes_context=True)
def voz_firmada(context, texto):
    request = context.get('request')
    usuario = getattr(request, 'user', None)
    if not texto or not puede_usar(usuario):
        return ''
    return signing.dumps({'u': usuario.pk, 't': str(texto)}, salt=SAL, compress=True)
