import calendar
import re
from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from .. import fechas
from ..dinero import suma
from .. import encuesta as encuesta_mod
from .. import legal, push
from ..models import Deuda, GastoPendiente, MetaAhorro, Presupuesto, Transaccion
from ..servicios.cuotas import proyecciones_deuda_activas
from ..servicios.esfera import estado_esfera
from ..servicios.esfera_bienvenida import bienvenida_esfera
from ..servicios.mes import MESES_LARGOS, nombre_mes_es, resumen_mes, salud_financiera
from ..servicios.panel import insights_panel, primeros_pasos, serie_seis_meses
from ..servicios.pendientes import calendario_del_mes, pendientes_del_mes
from ..servicios.ritmo import ritmo_del_mes
from ..servicios.suscripciones import generar_cobros_suscripciones
from .comun import contadores, simbolo_de


PATRON_CUOTA = re.compile(r'^Cuota (\d+)/(\d+)\s*[—-]\s*(.+)$')


def textos_movimiento(t):
    desc = (t.descripcion or '').strip()
    cat = t.nombre_categoria
    if t.es_cuota:
        m = PATRON_CUOTA.match(desc)
        if m:
            return m.group(3), f'Cuota {m.group(1)} de {m.group(2)}'
        return desc or cat, 'Cuota'
    if t.es_cobro_suscripcion:
        return t.nombre_sin_prefijo or cat, 'Suscripción'
    if t.es_cuenta_pendiente:
        return t.nombre_sin_prefijo or cat, 'Cuenta por pagar'
    if not desc:
        return cat, 'Ingreso' if t.es_ingreso else 'Gasto'
    return desc, cat


def _mes_pedido(request, hoy):
    try:
        year = int(request.GET.get('year', hoy.year))
        month = int(request.GET.get('month', hoy.month))
        date(year, month, 1)
    except ValueError:
        return hoy.year, hoy.month
    return year, month


@login_required(login_url='/login/')
def calendario_inicio(request):
    hoy = fechas.hoy()
    year, month = _mes_pedido(request, hoy)
    r = resumen_mes(request.user, year, month)
    todas_las_deudas = list(Deuda.objects.filter(usuario=request.user).prefetch_related('pagos'))
    calendario_datos, dias_con_pago = calendario_del_mes(year, month, hoy, r['eventos'])
    pagos_mes = pendientes_del_mes(request.user, year, month, todas_las_deudas)
    sin_pagar = [i for i in pagos_mes if not i['pagado']]
    respuesta = render(request, 'finanzas/_inicio_calendario.html', {
        'nombre_mes': nombre_mes_es(year, month),
        'year': year, 'month': month,
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
        'calendario': calendario_datos,
        'dias_con_pago': dias_con_pago,
        'pendientes': pagos_mes,
        'monto_sin_pagar': round(suma(i['monto'] for i in sin_pagar)),
        'monto_ya_pagado': round(suma(i['monto'] for i in pagos_mes if i['pagado'])),
        'gastos_pendientes': GastoPendiente.objects.filter(usuario=request.user, pagado=False),
    })
    respuesta['Cache-Control'] = 'no-store'
    return respuesta


def _movimientos_del_mes(usuario, year, month):
    _, ultimo = calendar.monthrange(year, month)
    movimientos_mes = list(Transaccion.objects.filter(
        usuario=usuario, fecha__gte=date(year, month, 1), fecha__lte=date(year, month, ultimo),
    ).order_by('-fecha', '-id'))
    for t in movimientos_mes:
        t.nombre_lista, t.meta_lista = textos_movimiento(t)
    mov_entro = round(suma(t.monto for t in movimientos_mes if t.es_ingreso))
    mov_salio = round(suma(t.monto for t in movimientos_mes if not t.es_ingreso))
    mov_cuotas = round(suma(t.monto for t in movimientos_mes if t.es_cuota))
    mov_tope = max(mov_entro, mov_salio, 1)
    return {
        'movimientos_mes': movimientos_mes,
        'mov_entro': mov_entro,
        'mov_salio': mov_salio,
        'mov_pct_unicos': round((mov_salio - mov_cuotas) / mov_tope * 100),
        'mov_pct_cuotas': round(mov_cuotas / mov_tope * 100),
        'mov_pct_salio': round(mov_salio / mov_entro * 100) if mov_entro else None,
        'mov_n_unicos': sum(1 for t in movimientos_mes if not t.es_ingreso and not t.es_cuota),
        'mov_n_cuotas': sum(1 for t in movimientos_mes if t.es_cuota),
        'mov_n_ingresos': sum(1 for t in movimientos_mes if t.es_ingreso),
    }


@login_required(login_url='/login/')
def movimientos_inicio(request):
    hoy = fechas.hoy()
    year, month = _mes_pedido(request, hoy)
    respuesta = render(request, 'finanzas/_inicio_movimientos.html', {
        'nombre_mes': nombre_mes_es(year, month),
        'volver': f"{reverse('dashboard')}?year={year}&month={month}",
        **_movimientos_del_mes(request.user, year, month),
    })
    respuesta['Cache-Control'] = 'no-store'
    return respuesta


@login_required(login_url='/login/')
def dashboard(request):
    generar_cobros_suscripciones(request.user)
    hoy = fechas.hoy()
    year, month = _mes_pedido(request, hoy)

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    r = resumen_mes(request.user, year, month)
    nombre_mes = nombre_mes_es(year, month)
    todas_las_deudas = list(Deuda.objects.filter(usuario=request.user).prefetch_related('pagos'))

    meses_labels, _, datos_gastos, datos_cuotas = serie_seis_meses(
        request.user, hoy, year, month, r)

    pendientes = [d for d in todas_las_deudas
                  if not d.esta_saldada and d.dias_para_vencer is not None]
    pendientes.sort(key=lambda d: d.dias_para_vencer)

    pagos_mes = pendientes_del_mes(request.user, year, month, todas_las_deudas)
    sin_pagar = [i for i in pagos_mes if not i['pagado']]
    atrasados = [i for i in sin_pagar if i['atrasado']]

    ultimas = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]
    metas = list(MetaAhorro.objects.filter(usuario=request.user)[:3])

    presupuesto = Presupuesto.objects.filter(usuario=request.user).first()
    proyecciones_deuda = proyecciones_deuda_activas(todas_las_deudas)
    insights, _ = insights_panel(
        r, datos_gastos, pendientes, proyecciones_deuda, presupuesto)
    if (year, month) == (hoy.year, hoy.month):
        insights = ritmo_del_mes(request.user, hoy, simbolo_de(request.user)) + insights

    context = {
        'nombre_mes': nombre_mes,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'es_mes_actual': (year, month) == (hoy.year, hoy.month),
        'prev_month_nombre': nombre_mes_es(prev_year, prev_month),
        'next_month_nombre': nombre_mes_es(next_year, next_month),

        'total_ingresos': round(r['ingresos']),
        'total_gastos': round(r['gastos']),
        'total_gastos_mes': round(r['gastos']) + round(r['total_cuotas_mes']),
        'total_cuotas_mes': round(r['total_cuotas_mes']),
        'disponible': round(r['disponible']),

        'atrasado_arrastrado': round(r['atrasado_arrastrado']),
        'cuotas_arrastradas': r['cuotas_arrastradas'],
        'n_cuotas_arrastradas': len(r['cuotas_arrastradas']),
        'por_pagar': round(r['cuotas_pendientes_mes'] + r['servicios_pendientes_mes']
                           + r['debo_pendiente_mes']),
        'dias_restantes': r['dias_restantes'],
        'por_dia': round(r['por_dia']),
        'pct_gastado': r['pct_gastado'],
        'pct_por_pagar': r['pct_por_pagar'],
        'pct_disponible': r['pct_disponible'],

        'pendientes': pagos_mes,
        'pendientes_sin_pagar': sin_pagar,
        'pendientes_atrasados': atrasados,
        'monto_sin_pagar': round(suma(i['monto'] for i in sin_pagar)),

        'insights': insights,
        'ultimas': ultimas,
        'metas': metas,

        'abrir_panel': bool(request.GET.get('registrar')),

        'meses_json': meses_labels,
        'gastos_json': datos_gastos,
        'cuotas_json': datos_cuotas,
    }

    f_ant = date(year, month, 1) - relativedelta(months=1)
    context['mes_anterior_nombre'] = MESES_LARGOS[f_ant.month - 1]

    pasos, pasos_hechos = primeros_pasos(request.user)
    context['primeros_pasos'] = pasos if pasos_hechos < len(pasos) else None
    context['pasos_hechos'] = pasos_hechos
    context['pasos_total'] = len(pasos)
    context['pasos_pct'] = int(pasos_hechos * 100 / len(pasos))

    context.update(contadores(
        request.user,
        resumen_actual=r if (year, month) == (hoy.year, hoy.month) else None,
    ))
    context['esfera'] = estado_esfera(
        request.user, r, presupuesto, month, (year, month) == (hoy.year, hoy.month),
        simbolo_de(request.user))
    if (year, month) != (hoy.year, hoy.month):
        context.update(salud_financiera(request.user, resumen_actual=r))
    context['salud_estado_mes'] = context.get('salud_estado') or 'neutro'
    if request.session.pop('bienvenida_esfera', False) and (year, month) == (hoy.year, hoy.month):
        perfil = context['profile']
        estado = context['esfera']['estado']
        context['bienvenida'] = {
            **bienvenida_esfera(estado, perfil.esfera_estado_visto),
            'nombre': (perfil.nombre_display or '').split(' ')[0],
        }
        if estado != 'neutro' and perfil.esfera_estado_visto != estado:
            perfil.esfera_estado_visto = estado
            perfil.save(update_fields=['esfera_estado_visto'])
    context['push_clave'] = push.clave_publica()
    if (context['push_clave'] and (year, month) == (hoy.year, hoy.month)
            and not request.user.suscripciones_push.exists()):
        proximos = [i for i in sin_pagar if 0 <= (i['fecha'] - hoy).days <= 7]
        if proximos:
            p = min(proximos, key=lambda i: i['fecha'])
            dias = (p['fecha'] - hoy).days
            cuando = 'Hoy' if dias == 0 else 'Mañana' if dias == 1 else f'El {p["fecha"].day}'
            context['push_invitacion'] = (f'{cuando} vence {p["nombre"]}. Te avisamos el día '
                                          'antes de cada cobro, nada más.')
    context['politica_pendiente'] = context['profile'].politica_version != legal.VERSION
    context['politica_version'] = legal.VERSION
    context['politica_vigente'] = legal.VIGENTE_DESDE
    context['politica_cambios'] = legal.CAMBIOS
    context['mostrar_encuesta'] = encuesta_mod.debe_mostrar(request)
    return render(request, 'finanzas/dashboard.html', context)
