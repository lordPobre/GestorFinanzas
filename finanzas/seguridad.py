"""Controles de seguridad propios.

Sin dependencias nuevas: todo se apoya en la caché de Django.

La caché TIENE que estar compartida entre procesos para que los contadores
de aquí signifiquen algo. En producción es DatabaseCache (ver CACHES en
core/settings.py): con LocMemCache y varios workers de gunicorn cada proceso
lleva su propia cuenta, y el tope de intentos se multiplica por el número de
workers sin que nada avise.
"""
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import redirect


def _ip(request):
    """La IP real del cliente detrás del proxy.

    X-Forwarded-For lo puede escribir cualquiera: un cliente que manda
    'X-Forwarded-For: 1.2.3.4' y lo cambia en cada petición se salta todo
    bloqueo por IP si se cree la primera entrada. Y eso es exactamente lo
    que hacía la versión anterior de esta función.

    Cómo se lee de verdad: cada proxy AÑADE al final la dirección de quien
    le habló. Con un proxy de confianza delante (Railway pone uno), el
    encabezado queda '<lo que invente el cliente>, <IP real>' y la buena es
    la ÚLTIMA. Con N proxies propios, la buena es la N-ésima contando desde
    el final. Lo que venga antes es texto del cliente y no se mira.

    PROXIES_CONFIABLES en settings dice cuántos son. Si es 0 (desarrollo),
    el encabezado se ignora entero y se usa REMOTE_ADDR.
    """
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

    # El proxy más externo escribe el primer tramo; el más cercano a la app,
    # el último. Se retrocede tantos tramos como proxies propios haya.
    indice = -n
    if len(tramos) < n:
        # Menos tramos que proxies declarados: alguien llegó por un camino
        # que no es el esperado. La entrada más antigua es lo más conservador
        # que se puede usar, y si falla se cae a la conexión directa.
        return tramos[0]
    return tramos[indice]


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
    restan = int(hasta - time.time())
    return max(0, restan)


def registrar_fallo(usuario, ip):
    """Suma un intento fallido.

    Se cuenta por usuario Y por IP a la vez: por usuario solo, cualquiera
    podría dejar fuera a otra persona fallando a propósito con su nombre;
    por IP sola, una red compartida se bloquearía entera.
    """
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
