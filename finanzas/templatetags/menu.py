from django import template

from .. import navegacion

register = template.Library()

CONTADORES = ('cuotas_activas', 'prestamos_activos', 'subs_pendientes')


@register.inclusion_tag('finanzas/_navegacion.html', takes_context=True)
def menu(context, modo):
    request = context.get('request')
    coincidencia = getattr(request, 'resolver_match', None)
    actual = coincidencia.url_name if coincidencia else None
    usuario = getattr(request, 'user', None)
    items = navegacion.armar(actual, {n: context.get(n) for n in CONTADORES},
                             bool(getattr(usuario, 'is_staff', False)))
    return {
        'modo': modo,
        'grupos': navegacion.lateral(items),
        'barra': navegacion.barra(items),
        'hoja': navegacion.hoja(items),
        'cuenta': navegacion.menu_cuenta(items),
        'mas_activo': navegacion.mas_activo(actual),
        'profile': context.get('profile'),
    }
