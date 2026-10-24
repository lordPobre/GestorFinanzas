
from django import template

from .. import fechas
from ..dinero import a_decimal
from ..servicios.mes import numeros_mes

register = template.Library()


@register.simple_tag(takes_context=True)
def estado_salud(context):
    request = context.get('request')
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return 'neutro'
    hoy = fechas.hoy()
    try:
        r = numeros_mes(usuario, hoy.year, hoy.month)
        ingresos = a_decimal(r.get('ingresos'))
        gastos = a_decimal(r.get('gastos'))
    except Exception:
        return 'neutro'
    if ingresos <= 0:
        return 'neutro'
    pct = gastos / ingresos * 100
    if pct >= 100:
        return 'rojo'
    if pct >= 80:
        return 'amarillo'
    return 'verde'
