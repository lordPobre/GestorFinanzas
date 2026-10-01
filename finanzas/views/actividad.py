from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .. import auditoria
from ..servicios.actividad import actividad as datos_actividad
from .comun import contadores


@login_required(login_url='/login/')
def actividad(request):
    contexto = datos_actividad(request.user)
    contexto['meses_conservacion'] = auditoria.DIAS_CONSERVACION // 30
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/actividad.html', contexto)
