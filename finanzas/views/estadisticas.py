import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from ..models import Deuda, Transaccion
from ..servicios.mes import NOMBRES_MESES, numeros_mes, resumen_mes
from .comun import contadores


@login_required(login_url='/login/')
def estadisticas(request):
    hoy = date.today()
    activas = [d for d in Deuda.objects.filter(usuario=request.user)
                                        .prefetch_related('pagos') if not d.esta_saldada]

    labels = [d.acreedor for d in activas]
    data_cuota = [float(d.monto_cuota) for d in activas]
    data_restante = [float(d.monto_restante) for d in activas]

    meses, ingresos, gastos = [], [], []
    resumen_actual = None
    for i in range(11, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        if i == 0:
            r = resumen_actual = resumen_mes(request.user, f.year, f.month)
        else:
            r = numeros_mes(request.user, f.year, f.month)
        meses.append(f'{NOMBRES_MESES[f.month - 1]} {f.year}')
        ingresos.append(r['ingresos'])
        gastos.append(r['gastos'] + r['total_cuotas_mes'])

    gastos_reales = [g for g in gastos if g > 0]
    promedio = sum(gastos_reales) / len(gastos_reales) if gastos_reales else 0
    ahorros = [ingresos[i] - gastos[i] for i in range(len(meses))]
    mejor = ahorros.index(max(ahorros)) if ahorros else None
    peor = gastos.index(max(gastos)) if gastos else None
    total_ing = sum(ingresos) or 1
    tasa_ahorro = round(sum(ahorros) / total_ing * 100, 1)

    def por_categoria(year, month):
        _, ult = calendar.monthrange(year, month)
        qs = Transaccion.objects.filter(
            usuario=request.user, tipo='EGRESO',
            fecha__gte=date(year, month, 1), fecha__lte=date(year, month, ult),
        ).values('categoria').annotate(total=Sum('monto'))
        return {x['categoria'] or 'Otros': float(x['total']) for x in qs}

    actual = por_categoria(hoy.year, hoy.month)
    anterior_f = date(hoy.year, hoy.month, 1) - relativedelta(months=1)
    anterior = por_categoria(anterior_f.year, anterior_f.month)
    maximo = max(actual.values()) if actual else 1
    etiquetas = dict(Transaccion.CATEGORIAS)

    ranking = []
    for cat, total in sorted(actual.items(), key=lambda x: -x[1]):
        antes = anterior.get(cat, 0)
        delta = round((total - antes) / antes * 100) if antes else None
        ranking.append({
            'nombre': cat,
            'label': etiquetas.get(cat, cat),
            'total': total,
            'ancho': round(total / maximo * 100),
            'delta': delta,
            'subio': delta is not None and delta > 0,
            'color': Transaccion.COLORES_CATEGORIA.get(cat, Transaccion.COLORES_CATEGORIA['Otros']),
        })

    context = {
        'labels_json': labels,
        'data_json': data_cuota,
        'data_restante_json': data_restante,
        'meses_json': meses,
        'ingresos_json': ingresos,
        'gastos_json': gastos,
        'promedio_gasto': round(promedio),
        'mejor_mes': meses[mejor] if mejor is not None else None,
        'mejor_ahorro': round(ahorros[mejor]) if mejor is not None else 0,
        'peor_mes': meses[peor] if peor is not None else None,
        'peor_gasto': round(gastos[peor]) if peor is not None else 0,
        'tasa_ahorro': tasa_ahorro,
        'ranking': ranking,
    }
    context.update(contadores(request.user, resumen_actual=resumen_actual))
    return render(request, 'finanzas/estadisticas.html', context)
