from datetime import date

from dateutil.relativedelta import relativedelta

from django.db.models import Sum
from django.urls import reverse

from ..models import Deuda, MetaAhorro, Presupuesto, Suscripcion, Transaccion
from .mes import NOMBRES_MESES, numeros_mes


def serie_seis_meses(usuario, hoy, year, month, resumen_actual):
    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = [], [], [], []
    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        if f.year == year and f.month == month:
            rr = resumen_actual
        else:
            rr = numeros_mes(usuario, f.year, f.month)
        meses_labels.append(f"{NOMBRES_MESES[f.month - 1]} {f.year}")
        datos_ingresos.append(rr['ingresos'])
        datos_gastos.append(rr['gastos'])
        datos_cuotas.append(rr['total_cuotas_mes'])
    return meses_labels, datos_ingresos, datos_gastos, datos_cuotas

def desglose_categorias(usuario, resumen):
    gastos_categoria = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=resumen['fecha_inicio'], fecha__lte=resumen['fecha_fin'],
    ).values('categoria').annotate(total=Sum('monto')).order_by('-total')

    total_cat = sum(float(x['total']) for x in gastos_categoria) or 1.0
    etiquetas = dict(Transaccion.CATEGORIAS)
    categorias = []
    for x in gastos_categoria:
        cat = x['categoria'] or 'Otros'
        categorias.append({
            'nombre': cat,
            'label': etiquetas.get(cat, cat),
            'total': float(x['total']),
            'porcentaje': round(float(x['total']) / total_cat * 100),
            'color': Transaccion.COLORES_CATEGORIA.get(cat, Transaccion.COLORES_CATEGORIA['Otros']),
        })
    return categorias

TONOS_INSIGHT = {
    'peligro': {'color': '#e25c5c', 'tenue': 'rgba(226,92,92,.14)',
                'borde': 'rgba(226,92,92,.32)', 'etiqueta': 'Urgente'},
    'alerta':  {'color': '#ffaa2c', 'tenue': 'rgba(255,170,44,.14)',
                'borde': 'rgba(255,170,44,.32)', 'etiqueta': 'Ojo con esto'},
    'exito':   {'color': '#53d258', 'tenue': 'rgba(83,210,88,.14)',
                'borde': 'rgba(83,210,88,.3)', 'etiqueta': 'Vas bien'},
    'info':    {'color': '#4b8cff', 'tenue': 'rgba(75,140,255,.14)',
                'borde': 'rgba(75,140,255,.28)', 'etiqueta': 'A este ritmo'},
}

def insights_panel(resumen, datos_gastos, pendientes, proyecciones_deuda, presupuesto):
    insights = []
    presupuesto_pct = None
    if presupuesto and presupuesto.limite_mensual > 0:
        limite = float(presupuesto.limite_mensual)
        presupuesto_pct = round((resumen['gastos'] / limite) * 100)
        if presupuesto_pct >= 100:
            insights.append({
                'tipo': 'peligro', 'icono': 'fa-exclamation-triangle',
                'texto': f'Superaste tu presupuesto mensual ({presupuesto_pct}%). Llevas gastado más de lo planeado.',
            })
        elif presupuesto_pct >= 80:
            insights.append({
                'tipo': 'alerta', 'icono': 'fa-exclamation-triangle',
                'texto': f'Vas en el {presupuesto_pct}% de tu presupuesto. Cuida los gastos del resto del mes.',
            })

    if len(datos_gastos) >= 2 and datos_gastos[-2] > 0:
        variacion = round(((datos_gastos[-1] - datos_gastos[-2]) / datos_gastos[-2]) * 100)
        if variacion >= 20:
            insights.append({'tipo': 'alerta', 'icono': 'fa-arrow-up',
                             'texto': f'Gastaste {variacion}% más que el mes pasado.'})
        elif variacion <= -20:
            insights.append({'tipo': 'exito', 'icono': 'fa-arrow-down',
                             'texto': f'Gastaste {abs(variacion)}% menos que el mes pasado. ¡Bien!'})

    urgentes = [d for d in pendientes if d.urgencia in ('vencida', 'critica')]
    for d in urgentes[:2]:
        dias = d.dias_para_vencer
        if dias < 0:
            insights.append({
                'tipo': 'peligro', 'icono': 'fa-credit-card',
                'texto': f'La cuota de {d.acreedor} está vencida hace {abs(dias)} día{"s" if abs(dias) != 1 else ""}.',
            })
        else:
            insights.append({
                'tipo': 'alerta', 'icono': 'fa-credit-card',
                'texto': f'La cuota de {d.acreedor} vence en {dias} día{"s" if dias != 1 else ""}.',
            })

    if proyecciones_deuda:
        prox = proyecciones_deuda[0]
        insights.append({
            'tipo': 'info', 'icono': 'fa-check-circle',
            'texto': f'A este ritmo, terminas de pagar {prox["acreedor"]} en {prox["mes_fin"]}.',
        })

    for i in insights:
        i.update(TONOS_INSIGHT.get(i['tipo'], TONOS_INSIGHT['info']))

    return insights, presupuesto_pct

def primeros_pasos(usuario):
    pasos = [
        {'titulo': 'Anota lo que entra',
         'nota': 'Tu sueldo o ingreso del mes',
         'icono': 'fa-arrow-down',
         'hecho': Transaccion.objects.filter(usuario=usuario, tipo='INGRESO').exists(),
         'url': '#', 'abrir': '#modalGasto', 'preset': 'INGRESO'},
        {'titulo': 'Anota un gasto',
         'nota': 'Para que el saldo del mes sea real',
         'icono': 'fa-plus',
         'hecho': Transaccion.objects.filter(usuario=usuario, tipo='EGRESO').exists(),
         'url': '#', 'abrir': '#modalGasto', 'preset': 'EGRESO'},
        {'titulo': 'Agrega tus compras en cuotas',
         'nota': 'La cuota queda puesta en cada mes',
         'icono': 'fa-credit-card',
         'hecho': Deuda.objects.filter(usuario=usuario).exists(),
         'url': reverse('deudas')},
        {'titulo': 'Suma tus suscripciones',
         'nota': 'Se cobran solas cada mes',
         'icono': 'fa-rotate',
         'hecho': Suscripcion.objects.filter(usuario=usuario).exists(),
         'url': reverse('suscripciones')},
        {'titulo': 'Crea una meta de ahorro',
         'nota': 'Cuánto juntar y para cuándo',
         'icono': 'fa-bullseye',
         'hecho': MetaAhorro.objects.filter(usuario=usuario).exists(),
         'url': reverse('metas')},
        {'titulo': 'Pon tu presupuesto del mes',
         'nota': 'Un techo para el día a día',
         'icono': 'fa-gauge-high',
         'hecho': Presupuesto.objects.filter(usuario=usuario).exists(),
         'url': reverse('perfil')},
    ]
    return pasos, sum(1 for p in pasos if p['hecho'])
