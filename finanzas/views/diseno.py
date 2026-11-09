from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .. import diseno


def _destino(request):
    siguiente = request.GET.get('next', '')
    if siguiente and url_has_allowed_host_and_scheme(
            siguiente, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(siguiente)
    return redirect('dashboard')


def probar(request):
    respuesta = _destino(request)
    respuesta.set_cookie(diseno.COOKIE, diseno.VALOR, max_age=diseno.DURACION,
                         secure=request.is_secure(), httponly=True, samesite='Lax')
    return respuesta


def volver(request):
    respuesta = _destino(request)
    respuesta.delete_cookie(diseno.COOKIE, samesite='Lax')
    return respuesta
