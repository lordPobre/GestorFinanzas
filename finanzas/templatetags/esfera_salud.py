from datetime import date

from django import template

from ..servicios.mes import resumen_mes

register = template.Library()


@register.simple_tag(takes_context=True)
def estado_salud(context):
    request = context.get('request')
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return 'neutro'
    hoy = date.today()
    try:
        r = resumen_mes(usuario, hoy.year, hoy.month)
        ingresos = float(r.get('ingresos') or 0)
        gastos = float(r.get('gastos') or 0)
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
