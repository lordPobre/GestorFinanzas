import calendar
import time
from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum

from ..models import Deuda, Suscripcion, Transaccion

MESES_LARGOS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def nombre_mes_es(year, month, capitalizado=True):
    """Mes en español.

    strftime('%B') usa el locale del SISTEMA, no LANGUAGE_CODE de Django, así
    que en el servidor devolvía 'August' aunque la app esté en español.
    """
    texto = f'{MESES_LARGOS[month - 1]} {year}'
    return texto.capitalize() if capitalizado else texto


def _decimal(valor):
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0))

def resumen_mes(usuario, year, month):
    """Los números del mes en un solo lugar.

    Antes esta lógica vivía dentro de dashboard(), así que el panel de
    registro, la vista de cuotas y el análisis no podían reusarla y cada
    pantalla mostraba un 'disponible' distinto. Ahora es una función.
    """
    _, ultimo_dia = calendar.monthrange(year, month)
    fecha_inicio = date(year, month, 1)
    fecha_fin = date(year, month, ultimo_dia)
    hoy = date.today()

    cero = Decimal('0')
    ingresos = Transaccion.objects.filter(
        usuario=usuario, tipo='INGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin,
    ).aggregate(t=Sum('monto'))['t'] or cero

    qs_gastos = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin, es_cuota=False,
    )
    gastos = qs_gastos.aggregate(t=Sum('monto'))['t'] or cero

    gastos_pagados = qs_gastos.filter(pagado=True).aggregate(t=Sum('monto'))['t'] or cero
    gastos_por_pagar = gastos - gastos_pagados

    periodo = year * 100 + month

    deudas = Deuda.objects.filter(usuario=usuario).prefetch_related('pagos')
    cuotas_pagadas = cero
    cuotas_pendientes = cero
    eventos = {}

    for d in deudas:
        if periodo not in d.periodos_programados:
            continue

        fecha_cobro = d.fecha_cobro_de(periodo)
        dia_venc = fecha_cobro.day

        pago = next((p for p in d.pagos.all() if p.periodo == periodo), None)
        estado = 'pagado' if pago else 'pendiente'

        monto_cuota = pago.monto if pago else d.monto_cuota_de(periodo)
        monto = _decimal(monto_cuota)

        if estado == 'pagado':
            cuotas_pagadas += monto
        else:
            cuotas_pendientes += monto

        eventos.setdefault(dia_venc, []).append({
            'deuda': d, 'estado': estado, 'monto': monto_cuota,
            'periodo': periodo, 'pago': pago,
            'atrasado': estado == 'pendiente' and fecha_cobro < hoy,
        })

    total_cuotas = cuotas_pagadas + cuotas_pendientes

    servicios_pagados = cero
    servicios_pendientes = cero
    for s in Suscripcion.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if periodo not in s.periodos_programados:
            continue
        monto = _decimal(s.monto)
        if s.esta_pagada_en(periodo):
            servicios_pagados += monto
        else:
            servicios_pendientes += monto

    atrasado_arrastrado = cero
    cuotas_arrastradas = []
    if (year, month) == (hoy.year, hoy.month):
        for d in deudas:
            for p in d.periodos_atrasados:
                if p >= periodo:
                    continue
                monto_p = _decimal(d.monto_cuota_de(p))
                atrasado_arrastrado += monto_p
                cuotas_arrastradas.append({
                    'deuda': d,
                    'periodo': p,
                    'monto': float(monto_p),
                    'etiqueta': nombre_mes_es(p // 100, p % 100),
                })
    cuotas_arrastradas.sort(key=lambda c: c['periodo'])

    comprometido = gastos + total_cuotas + atrasado_arrastrado
    disponible = ingresos - comprometido

    if (year, month) == (hoy.year, hoy.month):
        dias_restantes = max(1, ultimo_dia - hoy.day + 1)
    else:
        dias_restantes = ultimo_dia

    base = max(ingresos, Decimal('1'))
    libre = max(cero, disponible)
    return {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'ultimo_dia': ultimo_dia,
        'ingresos': float(ingresos),
        'gastos': float(gastos),
        'gastos_pagados': float(gastos_pagados),
        'gastos_por_pagar': float(gastos_por_pagar),
        'cuotas_pagadas_mes': float(cuotas_pagadas),
        'cuotas_pendientes_mes': float(cuotas_pendientes),
        'total_cuotas_mes': float(total_cuotas),
        'servicios_pagados_mes': float(servicios_pagados),
        'servicios_pendientes_mes': float(servicios_pendientes),
        'total_servicios_mes': float(servicios_pagados + servicios_pendientes),
        'atrasado_arrastrado': float(atrasado_arrastrado),
        'cuotas_arrastradas': cuotas_arrastradas,
        'comprometido': float(comprometido),
        'disponible': float(disponible),
        'exacto': {
            'ingresos': ingresos,
            'gastos': gastos,
            'total_cuotas_mes': total_cuotas,
            'comprometido': comprometido,
            'disponible': disponible,
        },
        'dias_restantes': dias_restantes,
        'por_dia': float(libre / dias_restantes),
        'pct_gastado': round(min(100, gastos / base * 100)),
        'pct_por_pagar': round(min(100, cuotas_pendientes / base * 100)),
        'pct_disponible': round(min(100, libre / base * 100)),
        'eventos': eventos,
    }

def salud_financiera(usuario, resumen_actual=None):
    """Puntaje 0-100 del mes en curso, para el bloque del sidebar.

    Tres cosas, con el peso que tienen en la vida real:
    que no gastes más de lo que entra, que las cuotas no te ahoguen,
    y que quede algo libre. Nada de esto necesita IA.

    Si quien llama ya calculó el resumen del mes en curso (el dashboard lo
    hace siempre), se puede pasar en 'resumen_actual' para no repetir las
    mismas consultas.
    """
    hoy = date.today()
    r = resumen_actual if resumen_actual is not None else resumen_mes(usuario, hoy.year, hoy.month)
    if r['ingresos'] <= 0:
        return {'salud_score': None, 'salud_label': '', 'salud_nota': ''}

    ingresos = r['ingresos']
    dti = r['total_cuotas_mes'] / ingresos * 100
    margen = r['disponible'] / ingresos * 100

    score = 100
    if r['disponible'] < 0:
        score -= 45
    elif margen < 10:
        score -= 20
    elif margen < 20:
        score -= 8

    if dti > 45:
        score -= 30
    elif dti > 35:
        score -= 18
    elif dti > 20:
        score -= 8

    gasto_pct = r['gastos'] / ingresos * 100
    if gasto_pct > 80:
        score -= 15
    elif gasto_pct > 65:
        score -= 6

    score = max(0, min(100, round(score)))

    if score >= 80:
        label = 'muy buena'
    elif score >= 60:
        label = 'buena'
    elif score >= 40:
        label = 'justa'
    else:
        label = 'apretada'

    if r['disponible'] < 0:
        nota = 'Este mes gastas más de lo que entra.'
    elif dti > 35:
        nota = f'El {round(dti)}% de lo que entra se va en cuotas.'
    elif margen < 10:
        nota = 'Te queda muy poco libre para imprevistos.'
    elif gasto_pct > 65:
        nota = f'Llevas gastado el {round(gasto_pct)}% de lo que entró.'
    else:
        nota = 'Gastas menos de lo que entra y las cuotas están bajo control.'

    return {'salud_score': score, 'salud_label': label, 'salud_nota': nota}


SEGUNDOS_NUMEROS_EN_CACHE = 7 * 24 * 60 * 60
CLAVES_NUMEROS = ('ingresos', 'gastos', 'total_cuotas_mes', 'disponible')


def _clave_version(usuario_id):
    return f'mes-version:{usuario_id}'


def _version(usuario_id):
    clave = _clave_version(usuario_id)
    version = cache.get(clave)
    if version is None:
        version = time.time_ns()
        cache.set(clave, version, None)
    return version


def invalidar(usuario_id):
    if usuario_id:
        cache.set(_clave_version(usuario_id), time.time_ns(), None)


def numeros_mes(usuario, year, month):
    hoy = date.today()
    if (year, month) == (hoy.year, hoy.month):
        r = resumen_mes(usuario, year, month)
        return {k: r[k] for k in CLAVES_NUMEROS}

    clave = f'mes:{usuario.pk}:{_version(usuario.pk)}:{year * 100 + month}'
    datos = cache.get(clave)
    if datos is None:
        r = resumen_mes(usuario, year, month)
        datos = {k: r[k] for k in CLAVES_NUMEROS}
        cache.set(clave, datos, SEGUNDOS_NUMEROS_EN_CACHE)
    return datos
