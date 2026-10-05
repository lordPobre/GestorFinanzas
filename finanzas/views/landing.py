import json
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .. import chat_ayuda, correo, legal
from ..seguridad import _ip, limitar, red, sumar
from .panel import dashboard


def inicio(request):
    if request.user.is_authenticated:
        return dashboard(request)
    if request.GET.get('fuente') == 'pwa':
        return redirect('login')
    return render(request, 'finanzas/landing.html', {'correo_contacto': legal.CORREO_CONTACTO})


@require_POST
@limitar(10, 3600, 'Llegaste al límite de preguntas por ahora.')
def ayuda_chat(request):
    try:
        datos = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False}, status=400)
    mensajes = chat_ayuda.limpiar(datos.get('mensajes') if isinstance(datos, dict) else None)
    if not mensajes:
        return JsonResponse({'ok': False}, status=400)
    usados, _ = sumar(f'chat-ip:{red(_ip(request))}:{date.today().isoformat()}', 26 * 3600)
    if usados > chat_ayuda.tope_por_ip():
        return JsonResponse({'ok': True, 'sin_respuesta': True})
    texto = chat_ayuda.responder(mensajes)
    if texto is None:
        return JsonResponse({'ok': True, 'sin_respuesta': True})
    return JsonResponse({'ok': True, 'texto': texto})


@require_POST
@limitar(3, 3600, 'Ya enviaste varios mensajes. Te respondemos pronto.')
def ayuda_contacto(request):
    if request.POST.get('sitio'):
        return JsonResponse({'ok': True})
    visita = request.POST.get('correo', '').strip()[:254]
    mensaje = request.POST.get('mensaje', '').strip()[:2000]
    try:
        validate_email(visita)
    except ValidationError:
        return JsonResponse({'ok': False, 'msg': 'Revisa el correo.'}, status=400)
    if not mensaje:
        return JsonResponse({'ok': False, 'msg': 'Escribe tu pregunta.'}, status=400)
    texto = f'Llegó una pregunta desde el chat de la landing.\n\nResponder a: {visita}\n\n{mensaje}\n'
    if not correo.enviar(legal.CORREO_CONTACTO, f'Pregunta desde la landing ({visita})', texto):
        return JsonResponse(
            {'ok': False, 'msg': f'No se pudo enviar. Escríbenos a {legal.CORREO_CONTACTO}.'}, status=502)
    return JsonResponse({'ok': True})
