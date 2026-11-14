from django.shortcuts import render

VERSION = '1.10'
VIGENTE_DESDE = '14 de noviembre de 2026'

RESPONSABLE = 'Carlos López Figueroa, Valparaíso, Chile'
CORREO_CONTACTO = 'soporte@perseustechnology.dev'

DOMINIO = 'fintora.cl'
REVISION_SEGURIDAD = 'octubre de 2026'
INFORME_SSL_LABS = f'https://www.ssllabs.com/ssltest/analyze.html?d={DOMINIO}'
INFORME_OBSERVATORY = f'https://developer.mozilla.org/es/observatory/analyze?host={DOMINIO}'
INFORME_INTERNET_NL = f'https://internet.nl/site/{DOMINIO}/'

CAMBIOS = (
    ('Anotar desde Telegram',
     'Si conectas el bot de Telegram, lo que le escribes o le grabas pasa por los servidores de '
     'Telegram, igual que sus respuestas. Fintora guarda el número del chat, tu nombre en Telegram, '
     'cuándo lo conectaste y la última vez que lo usaste. Los audios se pasan a texto con ElevenLabs '
     'y no se guardan.'),
    ('Frases que no se entienden solas',
     'Si tienes el análisis con IA activado y lo que anotas desde Telegram o con tu clave personal no '
     'se entiende en el servidor, esa frase se envía a Anthropic para leer el monto, la categoría y la '
     'fecha. No se envía nada más de tu cuenta.'),
)

MESES_INACTIVIDAD = 12
DIAS_GRACIA_INACTIVIDAD = 30

def _contexto(request=None):
    return {
        'legal_base': 'finanzas/legal_base_2c.html',
        'version': VERSION,
        'vigente_desde': VIGENTE_DESDE,
        'responsable': RESPONSABLE,
        'correo_contacto': CORREO_CONTACTO,
        'meses_inactividad': MESES_INACTIVIDAD,
        'dias_gracia_inactividad': DIAS_GRACIA_INACTIVIDAD,
    }

def privacidad(request):
    return render(request, 'finanzas/privacidad.html', _contexto(request))

def terminos(request):
    return render(request, 'finanzas/terminos.html', _contexto(request))

def seguridad(request):
    contexto = _contexto(request)
    contexto.update({
        'revision_seguridad': REVISION_SEGURIDAD,
        'informe_ssl_labs': INFORME_SSL_LABS,
        'informe_observatory': INFORME_OBSERVATORY,
        'informe_internet_nl': INFORME_INTERNET_NL,
    })
    return render(request, 'finanzas/seguridad.html', contexto)

def datos_legales(request):
    return {'legal': _contexto()}
