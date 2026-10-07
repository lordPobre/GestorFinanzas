from django.shortcuts import render

VERSION = '1.6'
VIGENTE_DESDE = '20 de octubre de 2026'

RESPONSABLE = 'Carlos López Figueroa, Valparaíso, Chile'
CORREO_CONTACTO = 'soporte@perseustechnology.dev'

DOMINIO = 'fintora.cl'
REVISION_SEGURIDAD = 'octubre de 2026'
INFORME_SSL_LABS = f'https://www.ssllabs.com/ssltest/analyze.html?d={DOMINIO}'
INFORME_OBSERVATORY = f'https://developer.mozilla.org/es/observatory/analyze?host={DOMINIO}'
INFORME_INTERNET_NL = f'https://internet.nl/site/{DOMINIO}/'

CAMBIOS = (
    ('Recordatorios en el teléfono',
     'Si los activas en Perfil, los avisos viajan cifrados por el servicio de avisos de tu '
     'navegador (Google, Apple, Mozilla o Microsoft), que no puede leerlos. Guardamos la '
     'dirección de tu aparato hasta que los apagas. Por defecto no muestran montos.'),
    ('Lo que debes',
     'En Préstamos → Debo puedes anotar a quién le debes plata. Como en Me deben, son datos '
     'de otras personas: anota lo mínimo. Si tienes recordatorios, el aviso puede decir su nombre.'),
    ('La voz de la esfera',
     'Si tienes el análisis con IA activado, la frase de la esfera se envía a ElevenLabs para '
     'leerla en voz alta: los montos de la pantalla y, en Me deben, los nombres de quienes te '
     'deben. Se apaga en Perfil → Análisis con IA.'),
    ('Plazos nuevos',
     'El audio de la voz se guarda 6 horas, y los aparatos desde los que entraste, mientras '
     'exista la cuenta.'),
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
