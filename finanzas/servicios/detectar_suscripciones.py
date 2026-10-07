import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from itertools import pairwise

from dateutil.relativedelta import relativedelta
from django.db.models import Q

from ..marcas import buscar_marca, normalizar
from ..models import SugerenciaDescartada, Suscripcion, Transaccion

MESES_ATRAS = 6
MINIMO_MESES = 3
TOLERANCIA = 0.10
DIAS_SIN_COBRO = 45
MAXIMO = 5

RUIDO = {
    'compra', 'compras', 'pago', 'pagos', 'pac', 'pat', 'cargo', 'cargos', 'cobro', 'nacional',
    'internacional', 'int', 'nac', 'www', 'com', 'cl', 'inc', 'ltda', 'spa', 'sa', 'cta', 'cte',
    'tarjeta', 'debito', 'credito', 'automatico', 'aut', 'mensual', 'suscripcion', 'plan',
}


def clave_de(descripcion):
    marca = buscar_marca(descripcion)
    if marca:
        return 'marca:' + normalizar(marca['nombre'])[:70]
    texto = re.sub(r'[^a-z ]+', ' ', normalizar(descripcion))
    palabras = [p for p in texto.split() if len(p) > 1 and p not in RUIDO]
    if not palabras:
        return None
    return 'texto:' + ' '.join(palabras[:3])[:70]


def _nombre_visible(clave, descripciones):
    marca = buscar_marca(descripciones[0])
    if marca:
        return marca['nombre']
    return clave.split(':', 1)[1].title()


def _ya_registrada(clave, nombre, subs):
    propio = normalizar(nombre)
    for s in subs:
        otro = normalizar(s.nombre)
        if clave_de(s.nombre) == clave or propio in otro or otro in propio:
            return True
    return False


def _meses_seguidos(periodos):
    seguidos = mejor = 1
    for a, b in pairwise(periodos):
        fa, fb = date(a // 100, a % 100, 1), date(b // 100, b % 100, 1)
        if fa + relativedelta(months=1) == fb:
            seguidos += 1
            mejor = max(mejor, seguidos)
        else:
            seguidos = 1
    return mejor


def sugerencias(usuario, hoy=None):
    hoy = hoy or date.today()
    desde = date(hoy.year, hoy.month, 1) - relativedelta(months=MESES_ATRAS)
    movimientos = (Transaccion.objects
                   .filter(usuario=usuario, tipo='EGRESO', es_cuota=False, suscripcion__isnull=True,
                           fecha__gte=desde, fecha__lte=hoy)
                   .exclude(descripcion='')
                   .exclude(Q(descripcion__startswith='Suscripción: ') | Q(descripcion__startswith='Pendiente: ') |
                            Q(descripcion__startswith='Cuota '))
                   .order_by('fecha', 'id'))

    grupos = defaultdict(list)
    for t in movimientos:
        clave = clave_de(t.descripcion)
        if clave:
            grupos[clave].append(t)

    descartadas = set(SugerenciaDescartada.objects.filter(usuario=usuario).values_list('clave', flat=True))
    subs = list(Suscripcion.objects.filter(usuario=usuario))
    salida = []
    for clave, lista in grupos.items():
        if clave in descartadas:
            continue
        por_mes = defaultdict(list)
        for t in lista:
            por_mes[t.fecha.year * 100 + t.fecha.month].append(t)
        if any(len(v) > 1 for v in por_mes.values()):
            continue
        periodos = sorted(por_mes)
        if len(periodos) < MINIMO_MESES or _meses_seguidos(periodos) < MINIMO_MESES:
            continue
        ultimo = por_mes[periodos[-1]][0]
        if (hoy - ultimo.fecha).days > DIAS_SIN_COBRO:
            continue
        montos = [float(por_mes[p][0].monto) for p in periodos]
        mediana = statistics.median(montos)
        if mediana <= 0 or any(abs(m - mediana) > mediana * TOLERANCIA for m in montos):
            continue
        nombre = _nombre_visible(clave, [t.descripcion for t in lista])
        if _ya_registrada(clave, nombre, subs):
            continue
        dia = round(statistics.median(por_mes[p][0].fecha.day for p in periodos))
        monto = round(float(ultimo.monto))
        salida.append({
            'clave': clave,
            'nombre': nombre[:100],
            'monto': monto,
            'anual': monto * 12,
            'dia': max(1, min(28, dia)),
            'meses': len(periodos),
            'categoria': Counter(t.categoria for t in lista).most_common(1)[0][0] or 'Suscripciones',
            'ids': [t.pk for t in lista],
            'cobrada_este_mes': periodos[-1] == hoy.year * 100 + hoy.month,
        })

    salida.sort(key=lambda s: -s['anual'])
    return salida[:MAXIMO]
