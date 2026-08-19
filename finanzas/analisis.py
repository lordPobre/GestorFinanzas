"""
Motor de análisis financiero predictivo (determinístico).
Calcula proyecciones de deuda, riesgo y salud financiera SIN IA.
La IA (opcional) interpreta estos números después, en otra capa.

Todo aquí es matemática financiera estándar, explicable y gratis.
"""
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from .models import Transaccion, Deuda


def _ingreso_promedio_mensual(usuario, meses=3):
    """Promedio de ingresos de los últimos N meses (más estable que un solo mes)."""
    hoy = date.today()
    total = 0.0
    meses_con_datos = 0
    for i in range(meses):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        _, ult = calendar.monthrange(f.year, f.month)
        ing = Transaccion.objects.filter(
            usuario=usuario, tipo='INGRESO',
            fecha__gte=date(f.year, f.month, 1),
            fecha__lte=date(f.year, f.month, ult),
        ).aggregate(t=Sum('monto'))['t'] or 0
        if ing > 0:
            total += float(ing)
            meses_con_datos += 1
    if meses_con_datos == 0:
        return 0.0
    return total / meses_con_datos


def _gasto_promedio_mensual(usuario, meses=3):
    """Promedio de gastos manuales (sin cuotas) de los últimos N meses."""
    hoy = date.today()
    total = 0.0
    meses_con_datos = 0
    for i in range(meses):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        _, ult = calendar.monthrange(f.year, f.month)
        gas = Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO', es_cuota=False,
            fecha__gte=date(f.year, f.month, 1),
            fecha__lte=date(f.year, f.month, ult),
        ).aggregate(t=Sum('monto'))['t'] or 0
        if gas > 0:
            total += float(gas)
            meses_con_datos += 1
    if meses_con_datos == 0:
        return 0.0
    return total / meses_con_datos


def analizar_finanzas(usuario):
    """
    Devuelve un diccionario completo con el análisis financiero del usuario.
    Todo calculado con matemática determinística.
    """
    deudas = Deuda.objects.filter(usuario=usuario)
    deudas_activas = [d for d in deudas if d.cuotas_pagadas < d.cuotas_totales]

    ingreso_mensual = _ingreso_promedio_mensual(usuario)
    gasto_mensual = _gasto_promedio_mensual(usuario)

    # --- Deuda total y cuota mensual comprometida ---
    deuda_total_restante = sum(float(d.monto_restante) for d in deudas_activas)
    cuota_mensual_total = sum(float(d.monto_cuota) for d in deudas_activas)

    # --- Ratio deuda/ingreso (DTI - Debt to Income) ---
    # Es el indicador estándar que usan los bancos.
    if ingreso_mensual > 0:
        dti = (cuota_mensual_total / ingreso_mensual) * 100
    else:
        dti = 0.0 if cuota_mensual_total == 0 else 100.0

    # --- Capacidad de pago: cuánto queda libre tras gastos y cuotas ---
    flujo_libre = ingreso_mensual - gasto_mensual - cuota_mensual_total

    # --- Meses restantes de deuda (la deuda que más tarda en pagarse) ---
    meses_restantes = 0
    fecha_libre_deudas = None
    for d in deudas_activas:
        cuotas_faltantes = d.cuotas_totales - d.cuotas_pagadas
        if cuotas_faltantes > meses_restantes:
            meses_restantes = cuotas_faltantes
            fecha_libre_deudas = d.fecha_fin_estimada

    # --- Proyección de deuda a 6 meses ---
    # Con el ritmo actual de pago de cuotas, cómo evoluciona la deuda total
    proyeccion = []
    hoy = date.today()
    nombres_meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

    # Gasto REAL del mes actual (gastos únicos ya registrados, sin cuotas).
    # Solo se suma al mes actual: los meses futuros no se pueden predecir.
    _, ult_actual = calendar.monthrange(hoy.year, hoy.month)
    gasto_real_mes_actual = float(Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO', es_cuota=False,
        fecha__gte=date(hoy.year, hoy.month, 1),
        fecha__lte=date(hoy.year, hoy.month, ult_actual),
    ).aggregate(t=Sum('monto'))['t'] or 0)

    # Para cada deuda, calculamos en qué mes calendario vence cada cuota pendiente.
    # Definición clave (según cómo lo piensa el usuario):
    #   - El SALDO de un mes es lo que aún debes DURANTE ese mes (antes de pagar
    #     la cuota que vence ese mes). La deuda "sigue en pie" hasta que la pagas.
    #   - Por eso el saldo baja a 0 el mes DESPUÉS de pagar la última cuota.
    #
    # Modelo: cada deuda tiene su próximo vencimiento. Las cuotas pendientes vencen
    # una por mes a partir de ahí. En un mes dado:
    #   - saldo = monto_cuota × (cuotas que todavía NO se han pagado al empezar el mes)
    #   - pago  = monto_cuota si vence (y aún no se pagó) una cuota ese mes
    for i in range(7):  # mes actual + 6
        f = date(hoy.year, hoy.month, 1) + relativedelta(months=i)
        saldo_del_mes = 0.0      # lo que aún debes durante el mes f
        pago_del_mes = 0.0       # cuota que se paga en el mes f
        for d in deudas_activas:
            cuotas_pendientes = d.cuotas_totales - d.cuotas_pagadas
            if cuotas_pendientes <= 0:
                continue
            prox = d.proximo_vencimiento
            if prox is None:
                continue
            # Mes (calendario) en que vence la PRÓXIMA cuota pendiente, como índice
            # relativo al mes actual (0 = este mes, 1 = mes siguiente, ...)
            offset_prox = (prox.year - hoy.year) * 12 + (prox.month - hoy.month)

            # ¿Cuántas cuotas quedan pendientes al COMENZAR el mes f?
            # Las cuotas pendientes vencen en offset_prox, offset_prox+1, ...
            # En el mes f (índice i) ya deberían haberse pagado las que vencían
            # ESTRICTAMENTE antes de f, es decir en meses < i.
            cuotas_vencidas_antes_de_f = max(0, i - offset_prox)
            cuotas_aun_pendientes = max(0, cuotas_pendientes - cuotas_vencidas_antes_de_f)

            # Saldo durante el mes f = lo que aún debe (incluye la cuota que vence
            # este mes, porque todavía no la ha pagado durante el mes)
            saldo_del_mes += float(d.monto_cuota) * cuotas_aun_pendientes

            # ¿Vence (y se paga) una cuota de esta deuda en el mes f?
            # Sí, si f coincide con uno de los meses de vencimiento pendientes:
            # offset_prox <= i <= offset_prox + (cuotas_pendientes - 1)
            if offset_prox <= i <= offset_prox + (cuotas_pendientes - 1):
                pago_del_mes += float(d.monto_cuota)

        # Solo el mes actual (i == 0) incluye los gastos únicos reales ya registrados
        pago_total_mes = pago_del_mes + (gasto_real_mes_actual if i == 0 else 0)
        proyeccion.append({
            'mes': f"{nombres_meses[f.month-1]} {f.year}",
            'deuda': round(saldo_del_mes),
            'pago_mes': round(pago_total_mes),
            'solo_cuotas': round(pago_del_mes),
            'es_mes_actual': i == 0,
        })

    # --- Score de riesgo (0-100, mayor = más riesgo) ---
    riesgo_score, riesgo_nivel, riesgo_factores = _calcular_riesgo(
        dti, flujo_libre, ingreso_mensual, cuota_mensual_total,
        len(deudas_activas), deuda_total_restante
    )

    # --- Tendencia: la deuda sube o baja ---
    if len(proyeccion) >= 2:
        if proyeccion[-1]['deuda'] < proyeccion[0]['deuda']:
            tendencia = 'bajando'
        elif proyeccion[-1]['deuda'] > proyeccion[0]['deuda']:
            tendencia = 'subiendo'
        else:
            tendencia = 'estable'
    else:
        tendencia = 'estable'

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
        'tiene_datos': ingreso_mensual > 0 or deuda_total_restante > 0,
    }


def _calcular_riesgo(dti, flujo_libre, ingreso, cuota_total, num_deudas, deuda_total):
    """
    Score de riesgo de endeudamiento (0-100).
    Basado en umbrales financieros reconocidos.
    """
    score = 0
    factores = []

    # Factor 1: DTI (ratio deuda/ingreso) — el más importante
    # <20% sano, 20-35% moderado, 35-45% alto, >45% crítico
    if dti > 45:
        score += 40
        factores.append({'factor': 'Ratio deuda/ingreso crítico', 'detalle': f'El {dti:.0f}% de tus ingresos va a deudas (lo sano es bajo 35%).', 'peso': 'alto'})
    elif dti > 35:
        score += 28
        factores.append({'factor': 'Ratio deuda/ingreso alto', 'detalle': f'El {dti:.0f}% de tus ingresos va a deudas.', 'peso': 'medio'})
    elif dti > 20:
        score += 12
        factores.append({'factor': 'Ratio deuda/ingreso moderado', 'detalle': f'El {dti:.0f}% de tus ingresos va a deudas.', 'peso': 'bajo'})

    # Factor 2: Flujo libre negativo — gastas más de lo que ganas
    if flujo_libre < 0:
        score += 30
        factores.append({'factor': 'Flujo mensual negativo', 'detalle': 'Tus gastos y cuotas superan tus ingresos.', 'peso': 'alto'})
    elif ingreso > 0 and flujo_libre < ingreso * 0.1:
        score += 15
        factores.append({'factor': 'Margen muy ajustado', 'detalle': 'Te queda muy poco libre cada mes.', 'peso': 'medio'})

    # Factor 3: Sin ingresos registrados pero con deuda
    if ingreso == 0 and deuda_total > 0:
        score += 20
        factores.append({'factor': 'Sin ingresos registrados', 'detalle': 'Tienes deudas pero no hay ingresos que las respalden.', 'peso': 'alto'})

    # Factor 4: Muchas deudas simultáneas
    if num_deudas >= 5:
        score += 10
        factores.append({'factor': 'Muchas deudas activas', 'detalle': f'Tienes {num_deudas} deudas al mismo tiempo.', 'peso': 'medio'})

    score = min(100, score)

    # Nivel según score
    if score >= 60:
        nivel = 'critico'
    elif score >= 35:
        nivel = 'alto'
    elif score >= 15:
        nivel = 'moderado'
    else:
        nivel = 'saludable'

    if not factores:
        factores.append({'factor': 'Situación saludable', 'detalle': 'Tus deudas están bajo control respecto a tus ingresos.', 'peso': 'bajo'})

    return score, nivel, factores
