from django import template

from .. import diseno

register = template.Library()


@register.simple_tag(takes_context=True)
def diseno_2c(context):
    return diseno.activo(context.get('request'))
