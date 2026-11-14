from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..servicios.indicadores import datos
from .comun import contadores


@login_required(login_url='/login/')
def indicadores(request):
    contexto = {'indicadores': datos()}
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/indicadores_2c.html', contexto)
