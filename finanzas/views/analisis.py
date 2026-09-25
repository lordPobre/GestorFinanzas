from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from ..seguridad import limitar
from ..servicios.cuotas import serie_cuotas
from .comun import contadores, get_or_create_profile, simbolo_de


@login_required(login_url='/login/')
def analisis_predictivo(request):
    from ..analisis import analizar_finanzas

    analisis = analizar_finanzas(request.user)
    circunferencia = 327
    riesgo_offset = circunferencia - (circunferencia * analisis['riesgo_score'] / 100)

    serie = serie_cuotas(request.user, atras=6, adelante=6)
    indice_actual = next((i for i, f in enumerate(serie) if f['es_mes_actual']), 0)

    context = {
        'analisis': analisis,
        'simbolo': simbolo_de(request.user),
        'riesgo_offset': round(riesgo_offset, 1),
        'serie': serie,
        'cuotas_atrasadas': analisis.get('cuotas_atrasadas', 0),
        'monto_atrasado': analisis.get('monto_atrasado', 0),
        'indice_actual': indice_actual,
        'total_pagado_serie': round(sum(f['pagado'] for f in serie)),
        'total_pendiente_serie': round(sum(f['pendiente'] for f in serie)),
        'serie_meses_json': [f['mes'] for f in serie],
        'serie_pagado_json': [round(f['pagado']) for f in serie],
        'serie_pendiente_json': [round(f['pendiente']) for f in serie],
        'serie_total_json': [round(f['total']) for f in serie],
        'serie_restante_json': [round(f['restante']) for f in serie],
        'proy_meses_json': [p['mes'] for p in analisis['proyeccion']],
        'proy_deuda_json': [p['deuda'] for p in analisis['proyeccion']],
        'proy_pago_json': [p['pago_mes'] for p in analisis['proyeccion']],
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/analisis.html', context)

@login_required(login_url='/login/')
@limitar(6, 3600, 'Ya pediste varias interpretaciones esta hora. '
                  'Los números de la pantalla no dependen de la IA.')
def analisis_ia(request):
    from ..analisis import analizar_finanzas
    from ..ia import interpretar_con_ia

    perfil_usuario = get_or_create_profile(request.user)
    if not perfil_usuario.analisis_ia:
        return JsonResponse({'ok': False, 'msg': 'Tienes el analisis con IA desactivado.',
                             'desactivado': True})

    analisis = analizar_finanzas(request.user)
    interpretacion = interpretar_con_ia(analisis, simbolo_de(request.user))
    if interpretacion:
        return JsonResponse({'ok': True, 'ia': interpretacion})
    return JsonResponse({'ok': False, 'msg': 'IA no disponible'})
