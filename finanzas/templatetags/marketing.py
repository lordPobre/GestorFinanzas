from django import template

from .. import marketing

register = template.Library()


def _datos(context):
    request = context.get('request')
    c = marketing.config()
    publica = bool(request is not None and marketing.es_publica(request))
    return {
        'm': c,
        'publica': publica,
        'pixeles': publica and marketing.hay_pixeles(c),
        'sitio': marketing.SITIO,
        'ruta': getattr(request, 'path', '/'),
        'csp_nonce': context.get('csp_nonce', ''),
    }


@register.inclusion_tag('finanzas/_marketing_head.html', takes_context=True)
def marketing_head(context):
    return _datos(context)


@register.inclusion_tag('finanzas/_consentimiento.html', takes_context=True)
def marketing_consentimiento(context):
    return _datos(context)


@register.simple_tag(takes_context=True)
def marketing_pixeles(context):
    return _datos(context)['pixeles']
