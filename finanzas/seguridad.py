import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect


def _ip(request):
    directa = request.META.get("REMOTE_ADDR", "desconocida")
    n = getattr(settings, "PROXIES_CONFIABLES", 0)
    if n <= 0:
        return directa

    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not reenviada:
        return directa

    tramos = [t.strip() for t in reenviada.split(",") if t.strip()]
    if not tramos:
        return directa

    indice = -n
    if len(tramos) < n:
        return tramos[0]
    return tramos[indice]


MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 15 * 60

MAX_POR_CUENTA = 20
VENTANA_CUENTA = 60 * 60

MAX_POR_IP = 50
VENTANA_IP = 60 * 60


def _clave_intentos(usuario, ip):
    return f"login:{usuario or '-'}:{ip}"


def _contadores(usuario, ip):
    salida = [(_clave_intentos(usuario, ip), MAX_INTENTOS, BLOQUEO_SEGUNDOS)]
    if usuario:
        salida.append((f"login-cuenta:{usuario}", MAX_POR_CUENTA, VENTANA_CUENTA))
    salida.append((f"login-ip:{ip}", MAX_POR_IP, VENTANA_IP))
    return salida


def esta_bloqueado(usuario, ip):
    restan = 0
    ahora = time.time()
    for clave, maximo, _ in _contadores(usuario, ip):
        datos = cache.get(clave)
        if datos and datos[0] >= maximo:
            restan = max(restan, int(datos[1] - ahora))
    return max(0, restan)


def registrar_fallo(usuario, ip):
    ahora = time.time()
    intentos_par = 0
    for clave, _, segundos in _contadores(usuario, ip):
        datos = cache.get(clave)
        intentos = (datos[0] if datos else 0) + 1
        cache.set(clave, (intentos, ahora + segundos), segundos)
        if not intentos_par:
            intentos_par = intentos
    return intentos_par


def limpiar_intentos(usuario, ip):
    cache.delete(_clave_intentos(usuario, ip))
    if usuario:
        cache.delete(f"login-cuenta:{usuario}")


def limitar(veces, segundos, mensaje=None):
    def decorador(vista):
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            uid = request.user.pk if request.user.is_authenticated else _ip(request)
            clave = f"limite:{vista.__name__}:{uid}"
            usados = cache.get(clave, 0)

            if usados >= veces:
                texto = mensaje or "Demasiadas peticiones. Espera un momento."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"ok": False, "msg": texto}, status=429)
                messages.warning(request, texto)
                return redirect("dashboard")

            cache.set(clave, usados + 1, segundos)
            return vista(request, *args, **kwargs)
        return envoltorio
    return decorador


def solo_propietario(modelo, campo_id, campo_usuario="usuario"):
    from django.shortcuts import get_object_or_404

    def decorador(vista):
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            pk = kwargs.get(campo_id)
            if pk is not None:
                get_object_or_404(modelo, pk=pk, **{campo_usuario: request.user})
            return vista(request, *args, **kwargs)
        return envoltorio
    return decorador
