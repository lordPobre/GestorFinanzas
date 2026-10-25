from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..models import ClaveApi
from ..seguridad import sumar
from .api import nueva_clave
from .comun import contadores


TOPE_CLAVES_HORA = 10


@login_required(login_url='/login/')
def clave_api(request):
    nueva = ''
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear':
            usadas, _ = sumar(f'clave_api:{request.user.pk}', 3600)
            if usadas > TOPE_CLAVES_HORA:
                messages.warning(request, 'Creaste varias claves seguidas. Espera un rato.')
                return redirect('clave_api')
            nueva = nueva_clave(request.user)
        elif accion == 'revocar':
            ClaveApi.objects.filter(usuario=request.user).delete()
            messages.success(request, 'Revocaste la clave. Lo que la usaba deja de funcionar.')
            return redirect('clave_api')
    ctx = {'clave': ClaveApi.objects.filter(usuario=request.user).first(), 'nueva': nueva}
    ctx.update(contadores(request.user))
    respuesta = render(request, 'finanzas/clave_api.html', ctx)
    respuesta['Cache-Control'] = 'no-store'
    return respuesta
