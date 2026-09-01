"""Controles de seguridad propios.

Sin dependencias nuevas: todo se apoya en la caché de Django, que en
PythonAnywhere y en local funciona en memoria sin configurar nada.

Si algún día montas más de un proceso (varios workers de gunicorn), la caché
en memoria NO se comparte entre ellos y los contadores se dividen. Ahí toca
pasar a Redis o Memcached; el código de aquí no cambia.
"""
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect


def _ip(request):
    """La IP real del cliente detrás del proxy.

    REMOTE_ADDR sería la del proxy, la misma para todos: bloquear por ella
    dejaría fuera a todo el mundo. Se toma la PRIMERA de X-Forwarded-For,
    que es la del cliente; las siguientes las añaden los intermediarios.
    """
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "desconocida")


# ============================================================
#  Intentos de acceso
# ============================================================

MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 15 * 60


def _clave_intentos(usuario, ip):
    return f"login:{usuario or '-'}:{ip}"


def esta_bloqueado(usuario, ip):
    """Cuántos segundos quedan de bloqueo, o 0 si no lo está."""
    datos = cache.get(_clave_intentos(usuario, ip))
    if not datos:
        return 0
    intentos, hasta = datos
    if intentos < MAX_INTENTOS:
        return 0
    import time
    restan = int(hasta - time.time())
    return max(0, restan)


def registrar_fallo(usuario, ip):
    """Suma un intento fallido.

    Se cuenta por usuario Y por IP a la vez: por usuario solo, cualquiera
    podría dejar fuera a otra persona fallando a propósito con su nombre;
    por IP sola, una red compartida se bloquearía entera.
    """
    import time
    clave = _clave_intentos(usuario, ip)
    datos = cache.get(clave)
    intentos = (datos[0] if datos else 0) + 1
    hasta = time.time() + BLOQUEO_SEGUNDOS
    cache.set(clave, (intentos, hasta), BLOQUEO_SEGUNDOS)
    return intentos


def limpiar_intentos(usuario, ip):
    """Al entrar bien se borra el contador: los fallos previos ya no cuentan."""
    cache.delete(_clave_intentos(usuario, ip))


# ============================================================
#  Límite de peticiones
# ============================================================

def limitar(veces, segundos, mensaje=None):
    """Tope de llamadas por usuario a una vista.

    Pensado para lo que cuesta dinero o tiempo: la interpretación con IA
    cobra por llamada, así que sin tope una pestaña en bucle vacía la cuota
    de la cuenta.
    """
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

            # El contador expira solo; no hace falta limpiarlo.
            cache.set(clave, usados + 1, segundos)
            return vista(request, *args, **kwargs)
        return envoltorio
    return decorador


# ============================================================
#  Propiedad de los datos
# ============================================================

def solo_propietario(modelo, campo_id, campo_usuario="usuario"):
    """Comprueba que el objeto sea del usuario que pide.

    Las vistas ya usan get_object_or_404(..., usuario=request.user), que es
    lo correcto. Este decorador está para las que se agreguen después: es
    fácil olvidar el filtro y exponer los datos de otro cambiando el id de
    la URL.
    """
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
