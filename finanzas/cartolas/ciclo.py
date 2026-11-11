import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

MESES = ('Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
         'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre')

DIA_CORTE = 20

CIERRE = re.compile(
    r'fecha\s+(?:de\s+)?(?:cierre|corte|facturaci[oó]n)[^\d]{0,20}'
    r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', re.I,
)

PERIODO = re.compile(
    r'per[ií]odo\s+(?:facturado|de\s+facturaci[oó]n)[^\d]{0,40}'
    r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})[^\d]{1,25}'
    r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', re.I,
)


def _fecha(d, m, a):
    if a < 100:
        a += 2000
    try:
        return date(a, m, d)
    except ValueError:
        return None


def periodo_facturado(texto):
    m = PERIODO.search(texto or '')
    if not m:
        return None, None
    n = [int(x) for x in m.groups()]
    desde, hasta = _fecha(*n[:3]), _fecha(*n[3:])
    if not (desde and hasta) or desde >= hasta or (hasta - desde).days > 62:
        return None, None
    return desde, hasta


def cierre_en_texto(texto):
    m = CIERRE.search(texto or '')
    if not m:
        return None
    d, mes, a = (int(x) for x in m.groups())
    return _fecha(d, mes, a)


def _mes_siguiente(f, dia):
    a, m = (f.year + 1, 1) if f.month == 12 else (f.year, f.month + 1)
    return date(a, m, min(dia, monthrange(a, m)[1]))


def cierre_por_dia(f):
    if f.day >= DIA_CORTE:
        return _mes_siguiente(f, DIA_CORTE - 1)
    return date(f.year, f.month, DIA_CORTE - 1)


def inicio_estimado(cierre):
    anterior = cierre.replace(day=1) - timedelta(days=1)
    return anterior.replace(day=min(cierre.day, anterior.day)) + timedelta(days=1)


def _mes(f):
    return MESES[f.month - 1].lower()


def _es_gasto(m):
    return m.tipo == 'EGRESO' and 'no es un gasto' not in m.aviso.lower()


def _mover(m, fecha, texto):
    m.fecha_compra = m.fecha
    m.fecha = fecha
    m.aviso = f'{m.aviso} {texto}' if m.aviso else texto


def _por_dia(cartola):
    gastos = [m for m in cartola.movimientos if _es_gasto(m)]
    compras = [m for m in gastos if not m.es_cuota]
    if not compras:
        return cartola
    primera, ultima = min(m.fecha for m in compras), max(m.fecha for m in compras)
    cierre = cierre_por_dia(ultima)
    un_estado = (ultima - primera).days <= 45

    for m in gastos:
        if m.es_cuota:
            if un_estado and m.fecha < inicio_estimado(cierre):
                m.fecha = cierre
            continue
        if m.fecha.day < DIA_CORTE:
            continue
        nueva = _mes_siguiente(m.fecha, DIA_CORTE - 1)
        _mover(m, nueva, (
            f'Compra del {m.fecha:%d/%m/%Y}. Las compras desde el día {DIA_CORTE} entran en el '
            f'estado de cuenta del mes siguiente, así que se anota en {_mes(nueva)}.'
        ))
    return cartola


def ajustar_al_ciclo(cartola, texto, cierre):
    desde, hasta = periodo_facturado(texto)
    cierre = hasta or cierre or cierre_en_texto(texto)
    if not cierre:
        return _por_dia(cartola)
    desde = desde or inicio_estimado(cierre)

    for m in cartola.movimientos:
        if not _es_gasto(m):
            continue
        if m.es_cuota:
            m.fecha = cierre
            continue
        if (m.fecha.year, m.fecha.month) >= (cierre.year, cierre.month):
            continue
        _mover(m, cierre, (
            f'Compra del {m.fecha:%d/%m/%Y}. Entra en el estado de cuenta '
            f'que cierra el {cierre:%d/%m}, así que se anota en {_mes(cierre)}.'
        ))

    cartola.periodo = (
        f'{MESES[cierre.month - 1]} {cierre.year} · '
        f'ciclo del {desde:%d/%m} al {cierre:%d/%m}'
    )
    return cartola


def reubicar_anteriores(cartola, usuario):
    from finanzas.models import Transaccion

    movidas = [m for m in cartola.movimientos if m.fecha_compra and not m.ya_existe]
    if not movidas:
        return cartola

    candidatas = list(Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__in={m.fecha_compra for m in movidas},
    ).order_by('pk'))
    usadas = set()

    for m in movidas:
        desc = m.descripcion.strip().lower()
        for t in candidatas:
            if t.pk in usadas or t.fecha != m.fecha_compra:
                continue
            if Decimal(t.monto) != m.monto or (t.descripcion or '').strip().lower() != desc:
                continue
            usadas.add(t.pk)
            m.mover_id = t.pk
            m.aviso = (
                f'Ya estaba anotada el {m.fecha_compra:%d/%m}, en {_mes(m.fecha_compra)}. '
                f'Al guardar se mueve a {_mes(m.fecha)}, el mes del ciclo en que se cobra.'
            )
            break

    return cartola
