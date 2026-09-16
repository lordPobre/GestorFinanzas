"""Páginas legales y datos del responsable del tratamiento.

Módulo propio y no un bloque más en views.py: son dos vistas que no
comparten nada con el resto de la aplicación, y tener la versión de la
política en un solo sitio es lo que permite registrar QUÉ texto aceptó cada
usuario.

Al publicar un cambio relevante en cualquiera de los dos documentos hay que
subir VERSION y VIGENTE_DESDE. El perfil compara la versión aceptada por el
usuario con esta constante, así que subirla es lo que hace aparecer el aviso
de "la política cambió".
"""
from django.shortcuts import render

VERSION = '1.0'
VIGENTE_DESDE = '16 de septiembre de 2026'

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
    }

def privacidad(request):
    """Pública a propósito: quien está decidiendo si se registra tiene que
    poder leerla antes de entregar nada."""
    return render(request, 'finanzas/privacidad.html', _contexto())

def terminos(request):
    return render(request, 'finanzas/terminos.html', _contexto())

def datos_legales(request):
    """Context processor: deja la versión y el contacto a mano en todas las
    plantillas, para el pie y para el aviso de política actualizada."""
    return {'legal': _contexto()}
