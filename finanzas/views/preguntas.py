from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ..ia_preguntas import (LARGO_PREGUNTA, MAX_TURNOS, cargar, conversacion_valida, gastar_pregunta,
                            nueva_conversacion, puede_preguntar, tope_diario, usadas_hoy)
from ..seguridad import limitar
from ..templatetags.voz import SAL as SAL_VOZ
from ..templatetags.voz import puede_usar
from .comun import get_or_create_profile, simbolo_de


def _con_voz(request, datos):
    if datos.get('ok') and datos.get('texto') and puede_usar(request.user):
        datos['voz'] = signing.dumps({'u': request.user.pk, 't': datos['texto']}, salt=SAL_VOZ, compress=True)
    return datos


@login_required(login_url='/login/')
@require_POST
@limitar(40, 3600, 'Ya hiciste varias preguntas esta hora.')
def preguntar(request):
    from ..tareas_ia import lanzar
    from ..tareas_ia import preguntar as tarea

    perfil = get_or_create_profile(request.user)
    if not perfil.analisis_ia:
        return JsonResponse({'ok': False, 'motivo': 'desactivado'}, status=403)
    if not puede_preguntar(perfil):
        return JsonResponse({'ok': False, 'motivo': 'politica'}, status=403)

    pregunta = ' '.join(request.POST.get('pregunta', '').split())[:LARGO_PREGUNTA]
    if not pregunta:
        return JsonResponse({'ok': False, 'motivo': 'vacia'}, status=400)

    conversacion = request.POST.get('conversacion', '')
    if not conversacion_valida(conversacion):
        conversacion = nueva_conversacion()
    if len(cargar(request.user.pk, conversacion)['turnos']) >= MAX_TURNOS:
        return JsonResponse({'ok': False, 'motivo': 'conversacion', 'conversacion': conversacion})
    if not gastar_pregunta(request.user.pk):
        return JsonResponse({'ok': False, 'motivo': 'tope', 'tope': tope_diario()})

    datos = lanzar(request.user, tarea, request.user.pk, conversacion, pregunta, simbolo_de(request.user))
    return JsonResponse(_con_voz(request, {**datos, 'conversacion': conversacion,
                                           'quedan_hoy': max(0, tope_diario() - usadas_hoy(request.user.pk))}))


@login_required(login_url='/login/')
@require_GET
def tarea_pregunta(request):
    from ..tareas_ia import SIN_IA, estado

    datos = estado(request.user, request.GET.get('t', ''))
    if datos is None:
        return JsonResponse({'listo': True, **SIN_IA}, status=404)
    return JsonResponse(_con_voz(request, datos))
