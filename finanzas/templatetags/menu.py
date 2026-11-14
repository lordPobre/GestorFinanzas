from django import template

from .. import navegacion

register = template.Library()


@register.inclusion_tag('finanzas/_navegacion.html', takes_context=True)
def menu(context, modo):
    request = context.get('request')
    coincidencia = getattr(request, 'resolver_match', None)
    actual = coincidencia.url_name if coincidencia else None
    usuario = getattr(request, 'user', None)
    barra = navegacion.barra_2c(actual)
    return {
        'modo': {'lateral': 'lateral', 'barra': 'barra2c'}.get(modo, modo),
        'dos_c': True,
        'grupos': [{'titulo': '', 'items': barra}],
        'barra': barra,
        'pestanas': navegacion.pestanas_2c(actual),
        'seccion': navegacion.seccion_2c(actual),
        'titulo': next((i['etiqueta'] for i in barra if i['activa']), 'Fintora'),
        'hoja': [],
        'cuenta': navegacion.menu_cuenta(navegacion.armar(actual, {}, bool(getattr(usuario, 'is_staff', False)))),
        'profile': context.get('profile'),
    }
