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
    """Promedio de los últimos N meses, contando los meses en cero.

    ANTES: se saltaban los meses sin movimiento (`if monto > 0`). Eso infla
    el promedio: un mes en que no gastaste nada es un dato real y bueno,
    excluirlo hacía parecer que gastas más de lo que gastas — y de ahí salía
    un riesgo más alto del que corresponde.

    Se cuentan solo los meses que ya empezaron, y se excluye el mes en curso
    porque está incompleto y arrastraría el promedio hacia abajo.
    """
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
    """El promedio de 3 meses cerrados. Si la cuenta es nueva y no hay
    historial, cae al mes en curso: es mejor un dato imperfecto que un cero
    que hace parecer que no tienes ingresos."""
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
    """El análisis completo del usuario, todo con matemática determinística."""
    deudas = list(Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'))

    # ANTES: `cuotas_pagadas < cuotas_totales`, un contador que no sabía qué
    # meses estaban pagados. Ahora se pregunta a los pagos registrados, igual
    # que el resto de la app — así esta página y la de cuotas dicen lo mismo.
    deudas_activas = [d for d in deudas if not d.esta_saldada]

    ingreso_mensual = _promedio_con_respaldo(usuario, 'INGRESO')
    gasto_mensual = _promedio_con_respaldo(usuario, 'EGRESO', solo_gastos_unicos=True)

    deuda_total_restante = sum(float(d.monto_restante) for d in deudas_activas)
    cuota_mensual_total = sum(float(d.monto_cuota) for d in deudas_activas)

    # --- Ratio deuda/ingreso (DTI), el indicador que usan los bancos ---
    if ingreso_mensual > 0:
        dti = (cuota_mensual_total / ingreso_mensual) * 100
    else:
        dti = 0.0 if cuota_mensual_total == 0 else 100.0

    flujo_libre = ingreso_mensual - gasto_mensual - cuota_mensual_total

    # --- Cuándo sales de deuda ---
    #
    # Es la deuda que termina más tarde. Se mide en meses pendientes reales,
    # no en `cuotas_totales - cuotas_pagadas`: si te adelantaste, sales antes,
    # y el número tiene que reflejarlo.
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

    # --- Proyección de deuda a 6 meses ---
    #
    # El saldo de un mes es lo que aún debes DURANTE ese mes: la cuota que
    # vence ese mes todavía cuenta, porque no la has pagado. Por eso el saldo
    # llega a cero el mes siguiente al último pago.
    #
    # ANTES esto se calculaba con aritmética de offsets sobre el contador
    # (`offset_prox`, `cuotas_vencidas_antes_de_f`), que asumía que las cuotas
    # se pagan una por mes sin adelantos ni atrasos. Ahora cada deuda ya sabe
    # qué meses le faltan, así que solo hay que contarlos.
    proyeccion = []
    hoy = date.today()

    for i in range(7):  # mes actual + 6
        f = date(hoy.year, hoy.month, 1) + relativedelta(months=i)
        periodo_f = f.year * 100 + f.month

        saldo_del_mes = 0.0
        pago_del_mes = 0.0
        for d in deudas_activas:
            pendientes = d.periodos_pendientes
            # Lo que aún debes durante el mes f: las cuotas pendientes cuyo
            # mes es f o posterior.
            for p in pendientes:
                if p >= periodo_f:
                    saldo_del_mes += float(d.monto_cuota_de(p))
            # Lo que se paga en el mes f, si ese mes tiene una cuota pendiente.
            if periodo_f in pendientes:
                pago_del_mes += float(d.monto_cuota_de(periodo_f))

        # ANTES el mes actual sumaba además los gastos únicos del mes, así que
        # la barra "Pagas ese mes" medía una cosa en el mes 0 y otra en el
        # resto. Comparar meses era imposible. Ahora la serie es solo cuotas,
        # y los gastos van por separado.
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

    # Cuotas que quedaron sin pagar: es plata que se debe HOY, no una
    # proyección. Antes no aparecía en ninguna parte del análisis.
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

    # Factor 1: DTI. <20% sano, 20-35% moderado, 35-45% alto, >45% crítico
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

    # Factor 2: flujo libre negativo
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

    # Factor 3: deuda sin ingresos que la respalden
    if ingreso == 0 and deuda_total > 0:
        score += 20
        factores.append({
            'factor': 'Sin ingresos registrados',
            'detalle': 'Tienes deudas pero no hay ingresos anotados. Registra tu sueldo para que el análisis sirva.',
            'peso': 'alto'})

    # Factor 4: muchas deudas al mismo tiempo
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
