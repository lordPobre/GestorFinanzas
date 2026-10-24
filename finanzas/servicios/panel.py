from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
from django.db.models import Exists, F, OuterRef, Sum
from django.urls import reverse

from ..categorias_base import COLOR_OTROS
from ..dinero import a_decimal, redondear
from ..models import Categoria, Deuda, MetaAhorro, Presupuesto, Suscripcion, Transaccion
from .mes import MESES_LARGOS, numeros_meses


def serie_seis_meses(usuario, hoy, year, month, resumen_actual):
    inicio = date(hoy.year, hoy.month, 1)
    meses = [((inicio - relativedelta(months=i)).year, (inicio - relativedelta(months=i)).month)
             for i in range(5, -1, -1)]
    otros = numeros_meses(usuario, [m for m in meses if m != (year, month)])
    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = [], [], [], []
    for mes in meses:
        rr = resumen_actual if mes == (year, month) else otros[mes]
        meses_labels.append(f"{MESES_LARGOS[mes[1] - 1]} {mes[0]}")
        datos_ingresos.append(rr['ingresos'])
        datos_gastos.append(rr['gastos'])
        datos_cuotas.append(rr['total_cuotas_mes'])
    return meses_labels, datos_ingresos, datos_gastos, datos_cuotas

def desglose_categorias(usuario, resumen):
    gastos_categoria = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=resumen['fecha_inicio'], fecha__lte=resumen['fecha_fin'],
    ).values(slug=F('categoria_ref__slug')).annotate(total=Sum('monto')).order_by('-total')

    total_cat = sum(float(x['total']) for x in gastos_categoria) or 1.0
    mapa = Categoria.mapa(usuario)
    categorias = []
    for x in gastos_categoria:
        cat = x['slug'] or 'Otros'
        datos = mapa.get(cat, {})
        categorias.append({
            'nombre': cat,
            'label': datos.get('label', cat),
            'total': float(x['total']),
            'porcentaje': round(float(x['total']) / total_cat * 100),
            'color': datos.get('color') or COLOR_OTROS,
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
        limite = a_decimal(presupuesto.limite_mensual)
        presupuesto_pct = redondear(a_decimal(resumen['gastos']) / limite * 100)
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
        variacion = redondear((a_decimal(datos_gastos[-1]) - a_decimal(datos_gastos[-2])) / a_decimal(datos_gastos[-2]) * 100)
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

def _existe(modelo, **filtros):
    return Exists(modelo.objects.filter(usuario=OuterRef('pk'), **filtros))

def primeros_pasos(usuario):
    hechos = get_user_model().objects.filter(pk=usuario.pk).values(
        paso_ingreso=_existe(Transaccion, tipo='INGRESO'),
        paso_gasto=_existe(Transaccion, tipo='EGRESO'),
        paso_cuotas=_existe(Deuda),
        paso_suscripciones=_existe(Suscripcion),
        paso_meta=_existe(MetaAhorro),
        paso_presupuesto=_existe(Presupuesto),
    ).first() or {}
    pasos = [
        {'titulo': 'Anota lo que entra',
         'nota': 'Tu sueldo o ingreso del mes',
         'icono': 'fa-arrow-down',
         'hecho': bool(hechos.get('paso_ingreso')),
         'url': '#', 'abrir': '#modalGasto', 'preset': 'INGRESO'},
        {'titulo': 'Anota un gasto',
         'nota': 'Para que el saldo del mes sea real',
         'icono': 'fa-plus',
         'hecho': bool(hechos.get('paso_gasto')),
         'url': '#', 'abrir': '#modalGasto', 'preset': 'EGRESO'},
        {'titulo': 'Agrega tus compras en cuotas',
         'nota': 'La cuota queda puesta en cada mes',
         'icono': 'fa-credit-card',
         'hecho': bool(hechos.get('paso_cuotas')),
         'url': reverse('deudas')},
        {'titulo': 'Suma tus suscripciones',
         'nota': 'Se cobran solas cada mes',
         'icono': 'fa-rotate',
         'hecho': bool(hechos.get('paso_suscripciones')),
         'url': reverse('suscripciones')},
        {'titulo': 'Crea una meta de ahorro',
         'nota': 'Cuánto juntar y para cuándo',
         'icono': 'fa-bullseye',
         'hecho': bool(hechos.get('paso_meta')),
         'url': reverse('metas')},
        {'titulo': 'Pon tu presupuesto del mes',
         'nota': 'Un techo para el día a día',
         'icono': 'fa-gauge-high',
         'hecho': bool(hechos.get('paso_presupuesto')),
         'url': reverse('perfil')},
    ]
    return pasos, sum(1 for p in pasos if p['hecho'])
