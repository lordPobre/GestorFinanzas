"""
Motor de análisis financiero determinístico.
Calcula proyecciones de deuda, riesgo y salud SIN IA.
La IA (opcional) interpreta estos números después, en otra capa.

Todo aquí es matemática financiera estándar, explicable y gratis.
"""
import calendar
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from .models import Deuda, Transaccion

NOMBRES_MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


def _promedio_mensual(usuario, tipo, meses=3, solo_gastos_unicos=False):
    hoy = date.today()
    total = 0.0
    contados = 0

    for i in range(1, meses + 1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        _, ult = calendar.monthrange(f.year, f.month)
        qs = Transaccion.objects.filter(
            usuario=usuario, tipo=tipo,
            fecha__gte=date(f.year, f.month, 1),
            fecha__lte=date(f.year, f.month, ult),
        )
        if solo_gastos_unicos:
            qs = qs.filter(es_cuota=False)
        total += float(qs.aggregate(t=Sum('monto'))['t'] or 0)
        contados += 1

    if contados == 0:
        return 0.0
    return total / contados


def _promedio_con_respaldo(usuario, tipo, solo_gastos_unicos=False):
    promedio = _promedio_mensual(usuario, tipo, 3, solo_gastos_unicos)
    if promedio > 0:
        return promedio

    hoy = date.today()
    _, ult = calendar.monthrange(hoy.year, hoy.month)
    qs = Transaccion.objects.filter(
        usuario=usuario, tipo=tipo,
        fecha__gte=date(hoy.year, hoy.month, 1),
        fecha__lte=date(hoy.year, hoy.month, ult),
    )
    if solo_gastos_unicos:
        qs = qs.filter(es_cuota=False)
    return float(qs.aggregate(t=Sum('monto'))['t'] or 0)


def analizar_finanzas(usuario):
    deudas = list(Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'))

    deudas_activas = [d for d in deudas if not d.esta_saldada]

    ingreso_mensual = _promedio_con_respaldo(usuario, 'INGRESO')
    gasto_mensual = _promedio_con_respaldo(usuario, 'EGRESO', solo_gastos_unicos=True)

    deuda_total_restante = sum(float(d.monto_restante) for d in deudas_activas)
    cuota_mensual_total = sum(float(d.monto_cuota) for d in deudas_activas)

    if ingreso_mensual > 0:
        dti = (cuota_mensual_total / ingreso_mensual) * 100
    else:
        dti = 0.0 if cuota_mensual_total == 0 else 100.0

    flujo_libre = ingreso_mensual - gasto_mensual - cuota_mensual_total

    meses_restantes = 0
    fecha_libre_deudas = None
    for d in deudas_activas:
        pendientes = d.periodos_pendientes
        if not pendientes:
            continue
        ultimo = pendientes[-1]
        fecha_ultimo = d.fecha_cobro_de(ultimo)
        faltan = (fecha_ultimo.year - date.today().year) * 12 + \
                 (fecha_ultimo.month - date.today().month) + 1
        if faltan > meses_restantes:
            meses_restantes = faltan
            fecha_libre_deudas = fecha_ultimo
    proyeccion = []
    hoy = date.today()

    for i in range(7):  # mes actual + 6
        f = date(hoy.year, hoy.month, 1) + relativedelta(months=i)
        periodo_f = f.year * 100 + f.month

        saldo_del_mes = 0.0
        pago_del_mes = 0.0
        for d in deudas_activas:
            pendientes = d.periodos_pendientes
            for p in pendientes:
                if p >= periodo_f:
                    saldo_del_mes += float(d.monto_cuota_de(p))
            if periodo_f in pendientes:
                pago_del_mes += float(d.monto_cuota_de(periodo_f))

        proyeccion.append({
            'mes': f'{NOMBRES_MESES[f.month - 1]} {f.year}',
            'deuda': round(saldo_del_mes),
            'pago_mes': round(pago_del_mes),
            'solo_cuotas': round(pago_del_mes),
            'es_mes_actual': i == 0,
        })

    riesgo_score, riesgo_nivel, riesgo_factores = _calcular_riesgo(
        dti, flujo_libre, ingreso_mensual, cuota_mensual_total,
        len(deudas_activas), deuda_total_restante,
    )

    # --- Tendencia ---
    if len(proyeccion) >= 2:
        if proyeccion[-1]['deuda'] < proyeccion[0]['deuda']:
            tendencia = 'bajando'
        elif proyeccion[-1]['deuda'] > proyeccion[0]['deuda']:
            tendencia = 'subiendo'
        else:
            tendencia = 'estable'
    else:
        tendencia = 'estable'

    cuotas_atrasadas = sum(len(d.periodos_atrasados) for d in deudas_activas)
    monto_atrasado = sum(float(d.monto_atrasado) for d in deudas_activas)

    return {
        'ingreso_mensual': round(ingreso_mensual),
        'gasto_mensual': round(gasto_mensual),
        'cuota_mensual_total': round(cuota_mensual_total),
        'deuda_total_restante': round(deuda_total_restante),
        'flujo_libre': round(flujo_libre),
        'dti': round(dti, 1),
        'meses_restantes': meses_restantes,
        'fecha_libre_deudas': fecha_libre_deudas,
        'proyeccion': proyeccion,
        'tendencia': tendencia,
        'riesgo_score': riesgo_score,
        'riesgo_nivel': riesgo_nivel,
        'riesgo_factores': riesgo_factores,
        'cantidad_deudas': len(deudas_activas),
        'cuotas_atrasadas': cuotas_atrasadas,
        'monto_atrasado': round(monto_atrasado),
        'tiene_datos': ingreso_mensual > 0 or deuda_total_restante > 0,
    }


def _calcular_riesgo(dti, flujo_libre, ingreso, cuota_total, num_deudas, deuda_total):
    """Score de riesgo de endeudamiento (0-100), sobre umbrales reconocidos."""
    score = 0
    factores = []
    if dti > 45:
        score += 40
        factores.append({
            'factor': 'Ratio deuda/ingreso crítico',
            'detalle': f'El {dti:.0f}% de lo que entra se va en cuotas. Lo sano es bajo 35%.',
            'peso': 'alto'})
    elif dti > 35:
        score += 28
        factores.append({
            'factor': 'Ratio deuda/ingreso alto',
            'detalle': f'El {dti:.0f}% de lo que entra se va en cuotas.',
            'peso': 'medio'})
    elif dti > 20:
        score += 12
        factores.append({
            'factor': 'Ratio deuda/ingreso moderado',
            'detalle': f'El {dti:.0f}% de lo que entra se va en cuotas.',
            'peso': 'bajo'})

    if flujo_libre < 0:
        score += 30
        factores.append({
            'factor': 'Gastas más de lo que entra',
            'detalle': f'Cada mes te faltan ${abs(int(flujo_libre)):,}'.replace(',', '.')
                       + ' para cubrir gastos y cuotas.',
            'peso': 'alto'})
    elif ingreso > 0 and flujo_libre < ingreso * 0.1:
        score += 15
        factores.append({
            'factor': 'Margen muy ajustado',
            'detalle': 'Te queda menos del 10% libre cada mes. Cualquier imprevisto te descuadra.',
            'peso': 'medio'})

    if ingreso == 0 and deuda_total > 0:
        score += 20
        factores.append({
            'factor': 'Sin ingresos registrados',
            'detalle': 'Tienes deudas pero no hay ingresos anotados. Registra tu sueldo para que el análisis sirva.',
            'peso': 'alto'})

    if num_deudas >= 5:
        score += 10
        factores.append({
            'factor': 'Muchas compras a plazo',
            'detalle': f'Tienes {num_deudas} pagando al mismo tiempo. Cada una es una fecha más que recordar.',
            'peso': 'medio'})

    score = min(100, score)

    if score >= 60:
        nivel = 'critico'
    elif score >= 35:
        nivel = 'alto'
    elif score >= 15:
        nivel = 'moderado'
    else:
        nivel = 'saludable'

    if not factores:
        factores.append({
            'factor': 'Situación saludable',
            'detalle': 'Tus deudas están bajo control respecto a lo que ganas.',
            'peso': 'bajo'})

    return score, nivel, factores
