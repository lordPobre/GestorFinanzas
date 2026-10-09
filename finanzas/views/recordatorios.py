import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .. import push
from ..models import SuscripcionPush, UserProfile

MAX_APARATOS = 10
SEGUNDOS_ENTRE_PRUEBAS = 30

OPCIONES = (
    ('push_vence', 'El día que vence', 'Cuotas, suscripciones, cuentas y lo que debes'),
    ('push_dia_antes', 'Un día antes', 'A las 9:00 del día anterior'),
    ('push_topes', 'Topes por categoría', 'Al llegar al 80 % y al pasarte'),
    ('push_resumen', 'Resumen del domingo', 'Cómo va el mes y lo que vence en la semana'),
    ('push_montos', 'Mostrar montos', ''),
)
CAMPOS_PUSH = tuple(c for c, _, _ in OPCIONES)


def opciones_de(perfil):
    filas = []
    for campo, titulo, nota in OPCIONES:
        activo = getattr(perfil, campo)
        if campo == 'push_montos':
            nota = ('Los avisos dicen cuánto es' if activo
                    else 'Apagado: el aviso no muestra la cifra en la pantalla bloqueada')
        filas.append({'campo': campo, 'titulo': titulo, 'nota': nota, 'activo': activo})
    return filas


def zona_valida(texto):
    texto = str(texto or '').strip()
    if not texto or len(texto) > 64 or '/' not in texto:
        return ''
    try:
        ZoneInfo(texto)
    except (ZoneInfoNotFoundError, ValueError):
        return ''
    return texto


def _json(request):
    try:
        datos = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return None
    return datos if isinstance(datos, dict) else None


@login_required(login_url='/login/')
@require_POST
def suscribir(request):
    if not push.disponible():
        return JsonResponse({'ok': False}, status=404)
    datos = _json(request)
    if datos is None:
        return JsonResponse({'ok': False}, status=400)
    endpoint = str(datos.get('endpoint') or '')
    claves = datos.get('keys') if isinstance(datos.get('keys'), dict) else {}
    p256dh = str(claves.get('p256dh') or '')
    auth = str(claves.get('auth') or '')
    if not push.endpoint_valido(endpoint) or not push.claves_validas(p256dh, auth):
        return JsonResponse({'ok': False}, status=400)
    SuscripcionPush.objects.update_or_create(endpoint=endpoint, defaults={
        'usuario': request.user, 'p256dh': p256dh, 'auth': auth,
        'agente': request.META.get('HTTP_USER_AGENT', '')[:200],
    })
    sobran = list(SuscripcionPush.objects.filter(usuario=request.user)
                  .order_by('-creada').values_list('pk', flat=True)[MAX_APARATOS:])
    if sobran:
        SuscripcionPush.objects.filter(pk__in=sobran).delete()
    zona = zona_valida(datos.get('zona'))
    if zona:
        UserProfile.objects.filter(usuario=request.user).update(zona_horaria=zona)
    return JsonResponse({'ok': True})


@login_required(login_url='/login/')
@require_POST
def quitar(request):
    datos = _json(request) or {}
    endpoint = str(datos.get('endpoint') or '')
    borradas, _ = SuscripcionPush.objects.filter(usuario=request.user, endpoint=endpoint).delete()
    return JsonResponse({'ok': True, 'borradas': borradas})


@login_required(login_url='/login/')
@require_POST
def probar(request):
    if not push.disponible():
        return JsonResponse({'ok': False}, status=404)
    if not cache.add(f'push-prueba:{request.user.pk}', 1, SEGUNDOS_ENTRE_PRUEBAS):
        return JsonResponse({'ok': False, 'msg': 'Espera unos segundos.'}, status=429)
    enviados = push.enviar_a_usuario(request.user, {
        'titulo': 'Así se ven los avisos de Fintora',
        'cuerpo': 'Te avisamos de tus cobros a las 9:00.',
        'url': '/perfil/',
        'etiqueta': 'prueba',
    })
    return JsonResponse({'ok': True, 'enviados': enviados})
