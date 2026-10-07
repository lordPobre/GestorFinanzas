import ipaddress
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone


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


def red(ip):
    try:
        direccion = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return ip or "desconocida"
    if direccion.version == 6:
        if direccion.ipv4_mapped:
            return str(direccion.ipv4_mapped)
        return str(ipaddress.ip_network(f"{direccion}/64", strict=False))
    return str(direccion)


MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 15 * 60

MAX_POR_CUENTA = 20
VENTANA_CUENTA = 60 * 60

MAX_POR_IP = 50
VENTANA_IP = 60 * 60


def _purgar_a_veces():
    if secrets.randbelow(100) == 0:
        from .models import Contador
        Contador.objects.filter(vence__lt=timezone.now()).delete()


def sumar(clave, segundos):
    from .models import Contador

    clave = clave[:200]
    ahora = timezone.now()
    vence = ahora + timedelta(seconds=segundos)
    for _ in range(2):
        try:
            with transaction.atomic():
                fila = Contador.objects.select_for_update().filter(clave=clave).first()
                if fila is None:
                    Contador.objects.create(clave=clave, cuenta=1, vence=vence)
                    _purgar_a_veces()
                    return 1, vence
                if fila.vence <= ahora:
                    Contador.objects.filter(pk=fila.pk).update(cuenta=1, vence=vence)
                    return 1, vence
                Contador.objects.filter(pk=fila.pk).update(cuenta=F("cuenta") + 1)
                return fila.cuenta + 1, fila.vence
        except IntegrityError:
            continue
    return 1, vence


def leer(clave):
    from .models import Contador
    fila = (Contador.objects.filter(clave=clave[:200], vence__gt=timezone.now())
            .values_list("cuenta", "vence").first())
    return fila or (0, None)


def borrar(*claves):
    from .models import Contador
    Contador.objects.filter(clave__in=[c[:200] for c in claves]).delete()


def _clave_intentos(usuario, ip):
    return f"login:{usuario or '-'}:{red(ip)}"


def _contadores(usuario, ip):
    salida = [(_clave_intentos(usuario, ip), MAX_INTENTOS, BLOQUEO_SEGUNDOS)]
    if usuario:
        salida.append((f"login-cuenta:{usuario}", MAX_POR_CUENTA, VENTANA_CUENTA))
    salida.append((f"login-ip:{red(ip)}", MAX_POR_IP, VENTANA_IP))
    return salida


def esta_bloqueado(usuario, ip):
    restan = 0
    ahora = timezone.now()
    for clave, maximo, _ in _contadores(usuario, ip):
        cuenta, vence = leer(clave)
        if vence and cuenta >= maximo:
            restan = max(restan, int((vence - ahora).total_seconds()))
    return max(0, restan)


def registrar_fallo(usuario, ip):
    intentos_par = 0
    for clave, _, segundos in _contadores(usuario, ip):
        intentos, _ = sumar(clave, segundos)
        if not intentos_par:
            intentos_par = intentos
    return intentos_par


def limpiar_intentos(usuario, ip):
    claves = [_clave_intentos(usuario, ip)]
    if usuario:
        claves.append(f"login-cuenta:{usuario}")
    borrar(*claves)


def limitar(veces, segundos, mensaje=None, destino="dashboard"):
    def decorador(vista):
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            uid = request.user.pk if request.user.is_authenticated else red(_ip(request))
            usados, _ = sumar(f"limite:{vista.__name__}:{uid}", segundos)

            if usados > veces:
                texto = mensaje or "Demasiadas peticiones. Espera un momento."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"ok": False, "msg": texto}, status=429)
                messages.warning(request, texto)
                return redirect(destino)

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
