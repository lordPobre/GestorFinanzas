import calendar
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from ..models import Categoria, TopeCategoria, Transaccion

UMBRAL_AVISO = 80


def gastado_por_categoria(usuario, year, month):
    _, ultimo = calendar.monthrange(year, month)
    return {
        x['categoria']: Decimal(x['total'])
        for x in Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO',
            fecha__gte=date(year, month, 1), fecha__lte=date(year, month, ultimo),
        ).values('categoria').annotate(total=Sum('monto'))
    }


def tono(pct):
    if pct >= 100:
        return 'rojo'
    if pct >= UMBRAL_AVISO:
        return 'amarillo'
    return 'verde'


def porcentaje(gastado, monto):
    return round(Decimal(gastado) / Decimal(monto) * 100) if monto and monto > 0 else 0


def estado_tope(tope, gastado):
    monto = Decimal(tope.monto)
    gastado = Decimal(gastado or 0)
    pct = porcentaje(gastado, monto)
    return {
        'tope': round(monto),
        'gastado': round(gastado),
        'pct': pct,
        'ancho': min(100, pct),
        'tono': tono(pct),
        'queda': round(max(Decimal('0'), monto - gastado)),
        'exceso': round(max(Decimal('0'), gastado - monto)),
        'avisar': tope.avisar,
    }


def promedio_tres_meses(usuario, hoy):
    inicio_mes = date(hoy.year, hoy.month, 1)
    desde = inicio_mes - relativedelta(months=3)
    hasta = inicio_mes - timedelta(days=1)
    return {
        x['categoria']: round(Decimal(x['total']) / 3)
        for x in Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO', fecha__gte=desde, fecha__lte=hasta,
        ).values('categoria').annotate(total=Sum('monto'))
    }


def topes_para_anotar(usuario, hoy):
    topes = list(TopeCategoria.objects.filter(usuario=usuario, avisar=True))
    if not topes:
        return {}
    gastado = gastado_por_categoria(usuario, hoy.year, hoy.month)
    mapa = Categoria.mapa(usuario)
    return {
        t.categoria: [mapa.get(t.categoria, {}).get('label', t.categoria),
                      float(t.monto), float(gastado.get(t.categoria, 0))]
        for t in topes
    }
