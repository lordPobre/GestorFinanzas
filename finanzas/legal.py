from django.shortcuts import render

VERSION = '1.2'
VIGENTE_DESDE = '1 de octubre de 2026'

RESPONSABLE = 'Carlos López Figueroa, Valparaíso, Chile'
CORREO_CONTACTO = 'soporte@perseustechnology.dev'

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

def datos_legales(request):
    return {'legal': _contexto()}
