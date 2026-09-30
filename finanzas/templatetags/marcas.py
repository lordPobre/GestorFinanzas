from django import template

from ..marcas import buscar_marca

register = template.Library()


@register.simple_tag
def marca_de(texto):
    return buscar_marca(texto)
