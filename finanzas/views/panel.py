from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .. import encuesta as encuesta_mod
from ..models import (Categoria, Deuda, GastoPendiente, MetaAhorro, Presupuesto, Suscripcion,
    Transaccion)
from ..servicios.cuotas import mis_cuotas_detalle, proyecciones_deuda_activas
from ..servicios.mes import MESES_LARGOS, nombre_mes_es, numeros_mes, resumen_mes
from ..servicios.panel import desglose_categorias, insights_panel, primeros_pasos, serie_seis_meses
from ..servicios.pendientes import calendario_del_mes, pendientes_del_mes
from ..servicios.suscripciones import generar_cobros_suscripciones
from .comun import contadores


@login_required(login_url='/login/')
def dashboard(request):
    generar_cobros_suscripciones(request.user)
    hoy = date.today()

    try:
        year = int(request.GET.get('year', hoy.year))
        month = int(request.GET.get('month', hoy.month))
        date(year, month, 1)
    except ValueError:
        year, month = hoy.year, hoy.month

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    r = resumen_mes(request.user, year, month)
    nombre_mes = nombre_mes_es(year, month)
    todas_las_deudas = Deuda.objects.filter(usuario=request.user)

    calendario_datos, dias_con_pago = calendario_del_mes(year, month, hoy, r['eventos'])
    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = serie_seis_meses(
        request.user, hoy, year, month, r)
    categorias = desglose_categorias(request.user, r)

    pendientes = [d for d in todas_las_deudas
                  if not d.esta_saldada and d.dias_para_vencer is not None]
    pendientes.sort(key=lambda d: d.dias_para_vencer)
    proximo_pago = pendientes[0] if pendientes else None

    pagos_mes = pendientes_del_mes(request.user, year, month)
    sin_pagar = [i for i in pagos_mes if not i['pagado']]
    atrasados = [i for i in sin_pagar if i['atrasado']]

    mis_cuotas, deuda_pagada_total, deuda_bruta_total = mis_cuotas_detalle(request.user, hoy)

    ultimas = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]
    deuda_total = sum(float(d.monto_restante) for d in todas_las_deudas if not d.esta_saldada)
    metas = MetaAhorro.objects.filter(usuario=request.user)
    es_nuevo = (r['ingresos'] == 0 and r['gastos'] == 0 and not todas_las_deudas.exists())

    presupuesto = Presupuesto.objects.filter(usuario=request.user).first()
    proyecciones_deuda = proyecciones_deuda_activas(todas_las_deudas)
    insights, presupuesto_pct = insights_panel(
        r, datos_gastos, pendientes, proyecciones_deuda, presupuesto)
    se_libera = proyecciones_deuda[0] if proyecciones_deuda else None

    context = {
        'nombre_mes': nombre_mes,
        'es_nuevo': es_nuevo,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'es_mes_actual': (year, month) == (hoy.year, hoy.month),
        'prev_month_nombre': nombre_mes_es(prev_year, prev_month),
        'next_month_nombre': nombre_mes_es(next_year, next_month),
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],

        'total_ingresos': round(r['ingresos']),
        'total_gastos': round(r['gastos']),
        'total_cuotas_mes': round(r['total_cuotas_mes']),
        'cuotas_pagadas_mes': round(r['cuotas_pagadas_mes']),
        'cuotas_pendientes_mes': round(r['cuotas_pendientes_mes']),
        'ya_gaste': round(r['gastos']),
        'gastos_pagados': round(r['gastos_pagados']),
        'gastos_por_pagar': round(r['gastos_por_pagar']),
        'pct_gasto_pagado': (round(r['gastos_pagados'] / r['gastos'] * 100)
                             if r['gastos'] else 0),
        'total_comprometido_mes': round(r['comprometido']),
        'disponible': round(r['disponible']),

        'atrasado_arrastrado': round(r['atrasado_arrastrado']),
        'cuotas_arrastradas': r['cuotas_arrastradas'],
        'n_cuotas_arrastradas': len(r['cuotas_arrastradas']),
        'deuda_total': round(deuda_total),

        'mis_cuotas': mis_cuotas,
        'deuda_bruta_total': deuda_bruta_total,
        'deuda_pagada_total': deuda_pagada_total,
        'deuda_pct_pagado': (round(deuda_pagada_total / deuda_bruta_total * 100)
                             if deuda_bruta_total else 0),
        'cuota_mensual_total': round(sum(c['cuota'] for c in mis_cuotas)),
        'cuotas_atrasadas_total': sum(c['atrasadas'] for c in mis_cuotas),

        'fijo_mensual': round(
            sum(c['cuota'] for c in mis_cuotas)
            + sum(float(s.monto) for s in Suscripcion.objects.filter(
                usuario=request.user, activa=True))
        ),

        'por_pagar': round(r['cuotas_pendientes_mes'] + r['servicios_pendientes_mes']),
        'servicios_pendientes_mes': round(r['servicios_pendientes_mes']),
        'servicios_pagados_mes': round(r['servicios_pagados_mes']),
        'dias_restantes': r['dias_restantes'],
        'por_dia': round(r['por_dia']),
        'pct_gastado': r['pct_gastado'],
        'pct_por_pagar': r['pct_por_pagar'],
        'pct_disponible': r['pct_disponible'],
        'proximo_pago': proximo_pago,
        'se_libera': se_libera,
        'categorias': categorias,
        'dias_con_pago': dias_con_pago,

        'pendientes': pagos_mes,
        'pendientes_sin_pagar': sin_pagar,
        'pendientes_atrasados': atrasados,
        'monto_sin_pagar': round(sum(float(i['monto']) for i in sin_pagar)),
        'monto_ya_pagado': round(sum(float(i['monto']) for i in pagos_mes if i['pagado'])),
        'mes_al_dia': bool(pagos_mes) and not sin_pagar,

        'insights': insights,
        'presupuesto': presupuesto,
        'presupuesto_pct': presupuesto_pct,
        'proyecciones_deuda': proyecciones_deuda,
        'deudas': [e['deuda'] for dia in r['eventos'].values() for e in dia],
        'gastos_pendientes': GastoPendiente.objects.filter(usuario=request.user, pagado=False),
        'ultimas': ultimas,
        'metas': metas,
        'calendario': calendario_datos,

        'abrir_panel': bool(request.GET.get('registrar')),

        'meses_json': meses_labels,
        'ingresos_json': datos_ingresos,
        'gastos_json': datos_gastos,
        'cuotas_json': datos_cuotas,
        'cat_labels_json': [c['label'] for c in categorias],
        'cat_data_json': [c['total'] for c in categorias],
        'cat_colores_json': [c['color'] for c in categorias],
    }

    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    context['hoy_texto'] = (f'{dias_semana[hoy.weekday()]}, {hoy.day} '
                            f'{MESES_LARGOS[hoy.month - 1]} {hoy.year}')

    f_ant = date(year, month, 1) - relativedelta(months=1)
    r_ant = numeros_mes(request.user, f_ant.year, f_ant.month)
    saldo_ant = r_ant['disponible']
    if saldo_ant:
        var_saldo = round((r['disponible'] - saldo_ant) / abs(saldo_ant) * 100)
        context['variacion_saldo'] = var_saldo
        context['variacion_saldo_abs'] = abs(var_saldo)
    else:
        context['variacion_saldo'] = None
        context['variacion_saldo_abs'] = None
    context['mes_anterior_nombre'] = MESES_LARGOS[f_ant.month - 1]

    pasos, pasos_hechos = primeros_pasos(request.user)
    context['primeros_pasos'] = pasos if pasos_hechos < len(pasos) else None
    context['pasos_hechos'] = pasos_hechos
    context['pasos_total'] = len(pasos)
    context['pasos_pct'] = int(pasos_hechos * 100 / len(pasos))

    context['mapa_categorias'] = Categoria.mapa(request.user)
    context.update(contadores(
        request.user,
        resumen_actual=r if (year, month) == (hoy.year, hoy.month) else None,
    ))
    context['mostrar_encuesta'] = encuesta_mod.debe_mostrar(request)
    return render(request, 'finanzas/dashboard.html', context)
