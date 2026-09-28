from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from ..plan import ESTRATEGIAS, armar_plan, resumen_para_ia
from ..seguridad import limitar
from .comun import contadores, get_or_create_profile, simbolo_de


def _entero(valor, tope):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return 0
    return max(0, min(n, tope))


@login_required(login_url='/login/')
def plan_plata(request):
    plan = armar_plan(request.user)
    datos = {**plan['datos'], 'simbolo': simbolo_de(request.user)}
    context = {'plan': plan, 'plan_json': datos}
    context.update(contadores(request.user))
    return render(request, 'finanzas/plan.html', context)


@login_required(login_url='/login/')
@limitar(6, 3600, 'Ya pediste varias explicaciones esta hora. '
                  'Los números del plan no dependen de la IA.')
def plan_ia(request):
    from ..ia_plan import explicar_plan

    perfil = get_or_create_profile(request.user)
    if not perfil.analisis_ia:
        return JsonResponse({'ok': False, 'desactivado': True,
                             'msg': 'Tienes el análisis con IA desactivado.'})

    plan = armar_plan(request.user)
    if not plan['tiene_datos'] or plan['sobra'] <= 0:
        return JsonResponse({'ok': False, 'msg': 'Todavía no hay un plan que explicar.'})

    tope = plan['sobra']
    ahorro = _entero(request.GET.get('ahorro'), tope)
    extra = _entero(request.GET.get('extra'), tope) if plan['deudas'] else 0
    estrategia = request.GET.get('estrategia')
    if estrategia not in ESTRATEGIAS:
        estrategia = 'saldo'

    resumen, nombres = resumen_para_ia(plan, ahorro, extra, estrategia)
    parrafos = explicar_plan(resumen, nombres, simbolo_de(request.user))
    if not parrafos:
        return JsonResponse({'ok': False, 'msg': 'IA no disponible'})
    return JsonResponse({'ok': True, 'parrafos': parrafos})
