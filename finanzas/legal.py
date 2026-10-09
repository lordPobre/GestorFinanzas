from django.shortcuts import render

VERSION = '1.8'
VIGENTE_DESDE = '9 de noviembre de 2026'

RESPONSABLE = 'Carlos López Figueroa, Valparaíso, Chile'
CORREO_CONTACTO = 'soporte@perseustechnology.dev'

DOMINIO = 'fintora.cl'
REVISION_SEGURIDAD = 'octubre de 2026'
INFORME_SSL_LABS = f'https://www.ssllabs.com/ssltest/analyze.html?d={DOMINIO}'
INFORME_OBSERVATORY = f'https://developer.mozilla.org/es/observatory/analyze?host={DOMINIO}'
INFORME_INTERNET_NL = f'https://internet.nl/site/{DOMINIO}/'

CAMBIOS = (
    ('Movimientos repetidos con IA',
     'Si tienes el análisis con IA activado, cuando dos movimientos tienen el mismo monto y '
     'fechas cercanas pero no está claro si son el mismo, se envían a Anthropic las fechas, el '
     'monto, la categoría y las descripciones de ese par para que lo revise. No se envía nada '
     'más de tu cuenta, y nada se borra sin que lo confirmes.'),
)

MESES_INACTIVIDAD = 12
DIAS_GRACIA_INACTIVIDAD = 30

def _contexto():
    return {
        'version': VERSION,
        'vigente_desde': VIGENTE_DESDE,
        'responsable': RESPONSABLE,
        'correo_contacto': CORREO_CONTACTO,
        'meses_inactividad': MESES_INACTIVIDAD,
        'dias_gracia_inactividad': DIAS_GRACIA_INACTIVIDAD,
    }

def privacidad(request):
    return render(request, 'finanzas/privacidad.html', _contexto())

def terminos(request):
    return render(request, 'finanzas/terminos.html', _contexto())

def seguridad(request):
    contexto = _contexto()
    contexto.update({
        'revision_seguridad': REVISION_SEGURIDAD,
        'informe_ssl_labs': INFORME_SSL_LABS,
        'informe_observatory': INFORME_OBSERVATORY,
        'informe_internet_nl': INFORME_INTERNET_NL,
    })
    return render(request, 'finanzas/seguridad.html', contexto)

def datos_legales(request):
    return {'legal': _contexto()}
