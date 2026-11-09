from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .. import diseno


def _destino(request):
    siguiente = request.GET.get('next', '')
    if siguiente and url_has_allowed_host_and_scheme(
            siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(siguiente)
    return redirect('dashboard')


def _guardar(request, respuesta, valor):
    respuesta.set_cookie(diseno.COOKIE, valor, max_age=diseno.DURACION,
                         secure=request.is_secure(), httponly=True, samesite='Lax')
    return respuesta


def probar(request):
    respuesta = _destino(request)
    if diseno.para_todos():
        respuesta.delete_cookie(diseno.COOKIE, samesite='Lax')
        return respuesta
    return _guardar(request, respuesta, diseno.VALOR)


def volver(request):
    respuesta = _destino(request)
    if diseno.para_todos():
        return _guardar(request, respuesta, diseno.ACTUAL)
    respuesta.delete_cookie(diseno.COOKIE, samesite='Lax')
    return respuesta
