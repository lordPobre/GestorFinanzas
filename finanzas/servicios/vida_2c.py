import calendar
import math
from collections import defaultdict
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncMonth

from ..categorias_base import COLOR_OTROS
from ..dinero import a_decimal, redondear
from ..models import Categoria, Transaccion
from .mes import MESES_LARGOS

CERO = Decimal('0')
IZQ, DER, ARRIBA, BASE, ALTO = 40, 980, 20, 200, 210
TONOS_META = ('verde', 'azul', 'lila', 'ambar', 'coral', 'rosa')


def _num(valor):
    return f'{valor:.1f}'


def _pct(valor):
    return f'{valor:.2f}'


def _techo(valor):
    valor = max(float(valor), 1.0) * 1.06
    paso = 10 ** math.floor(math.log10(valor))
    for factor in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if valor <= factor * paso:
            return factor * paso
    return 10 * paso


def _indice(fecha):
    return fecha.year * 12 + fecha.month - 1


def _mes_texto(indice):
    return f'{MESES_LARGOS[indice % 12]} {indice // 12}'


def categorias_y_dias(usuario, r, plata, pagos, hoy):
    inicio, fin = r['fecha_inicio'], r['fecha_fin']
    previo = inicio - relativedelta(months=1)
    filas = list(Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO', fecha__gte=previo, fecha__lte=fin,
    ).values('fecha', 'es_cuota', slug=F('categoria_ref__slug')).annotate(total=Sum('monto')).order_by())
    en_curso = (inicio.year, inicio.month) == (hoy.year, hoy.month)
    categorias = _categorias(usuario, filas, inicio, previo, hoy if en_curso else None)
    return categorias, (_dia_a_dia(filas, r, plata, pagos, hoy) if en_curso else None)


def _categorias(usuario, filas, inicio, previo, hoy):
    actual, antes = defaultdict(lambda: CERO), defaultdict(lambda: CERO)
    for f in filas:
        slug = f['slug'] or 'Otros'
        if f['fecha'] >= inicio:
            actual[slug] += f['total']
        elif hoy is None or f['fecha'].day <= hoy.day:
            antes[slug] += f['total']
    total = sum(actual.values(), CERO) or 1
    mapa = Categoria.mapa(usuario)
    nombre_previo = MESES_LARGOS[previo.month - 1]
    sufijo = ' a esta fecha' if hoy else ''
    salida = []
    for slug, monto in sorted(actual.items(), key=lambda x: -x[1]):
        datos = mapa.get(slug, {})
        monto_previo = antes.get(slug, CERO)
        texto, tono = '', ''
        if monto_previo > 0:
            cambio = redondear((monto - monto_previo) / monto_previo * 100)
            if abs(cambio) < 3:
                texto = f'Igual que {nombre_previo}{sufijo}'
            elif cambio > 0:
                texto, tono = f'{cambio}% más que {nombre_previo}{sufijo}', 'sube'
            else:
                texto, tono = f'{-cambio}% menos que {nombre_previo}{sufijo}', 'baja'
        salida.append({
            'nombre': slug,
            'label': datos.get('label', slug),
            'total': monto,
            'porcentaje': redondear(monto / total * 100),
            'color': datos.get('color') or COLOR_OTROS,
            'delta_txt': texto,
            'delta_tono': tono,
        })
    return salida


def _dia_a_dia(filas, r, plata, pagos, hoy):
    dias = r['ultimo_dia']
    dia = hoy.day
    inicio = r['fecha_inicio']
    por_dia = [CERO] * (dias + 1)
    for f in filas:
        if f['es_cuota'] or f['fecha'] < inicio or f['fecha'] > hoy:
            continue
        por_dia[f['fecha'].day] += f['total']
    acum = [CERO]
    for d in range(1, dia + 1):
        acum.append(acum[-1] + por_dia[d])
    llevas = acum[-1]
    base = a_decimal(r['disponible']) + a_decimal(r['gastos'])
    toca_dia = base / dias if base > 0 else None
    sigue = llevas + llevas / dia * (dias - dia)
    techo = _techo(max(base if base > 0 else CERO, sigue, llevas))

    def x(d):
        return IZQ + d / dias * (DER - IZQ)

    def y(valor):
        return BASE - float(valor) / techo * (BASE - ARRIBA)

    puntos = [f'{_num(x(d))},{_num(y(v))}' for d, v in enumerate(acum)]
    marcas = sorted({1, 5, 10, 15, 20, 25, dias, dia})
    ejes = [{'izq': _pct(x(d) / 10), 'texto': 'Hoy' if d == dia else str(d), 'hoy': d == dia}
            for d in marcas if d == dia or abs(d - dia) > 2]
    marcados = []
    for p in pagos:
        fecha = p.get('fecha')
        if not isinstance(fecha, date) or (fecha.year, fecha.month) != (inicio.year, inicio.month):
            continue
        marcados.append({'izq': _pct(x(fecha.day) / 10), 'pagado': bool(p.get('pagado')),
                         'nombre': p.get('nombre', ''), 'monto': p.get('monto')})
    tocaba = toca_dia * dia if toca_dia else None
    datos = {
        'dia': dia,
        'dias': dias,
        'llevas': plata(llevas),
        'promedio': plata(llevas / dia),
        'base': plata(base) if toca_dia else None,
        'toca_dia': plata(toca_dia) if toca_dia else None,
        'tocaba': plata(tocaba) if toca_dia else None,
        'diferencia': plata(abs(tocaba - llevas)) if toca_dia else None,
        'sobre': bool(toca_dia and llevas > tocaba),
        'dias_bajo': sum(1 for d in range(1, dia + 1) if toca_dia and por_dia[d] <= toca_dia),
        'linea': ' '.join(puntos),
        'area': f'M{IZQ},{BASE} L' + ' L'.join(puntos) + f' L{_num(x(dia))},{BASE} Z',
        'hoy_x': _num(x(dia)),
        'hoy_y': _num(y(llevas)),
        'hoy_izq': _pct(x(dia) / 10),
        'hoy_arriba': _pct(y(llevas) / ALTO * 100),
        'fin_y': _num(y(sigue)),
        'fin_arriba': _pct(y(sigue) / ALTO * 100),
        'ritmo_y': _num(y(base)) if toca_dia else None,
        'ritmo_arriba': _pct(y(base) / ALTO * 100) if toca_dia else None,
        'grid': [{'y': _num(y(techo * k / 3)), 'arriba': _pct(y(techo * k / 3) / ALTO * 100),
                  'valor': Decimal(round(techo * k / 3))} for k in (1, 2, 3)],
        'ejes': ejes,
        'pagos': marcados,
    }
    return datos


def eta_meta(d, hoy):
    meta = d['meta']
    if meta.esta_completa:
        return None
    falta = a_decimal(meta.monto_faltante or 0)
    ritmo = a_decimal(d.get('aportado_6m') or 0) / 6
    ahora = _indice(hoy)
    llega = ahora + max(1, math.ceil(falta / ritmo)) if ritmo > 0 else None
    limite = _indice(meta.fecha_limite) if meta.fecha_limite else None
    quieta = d.get('meses_quieta')
    ultimo = d.get('ultimo_aporte')
    salida = {
        'llega': _mes_texto(llega) if llega is not None else '',
        'llega_indice': llega,
        'limite': _mes_texto(limite) if limite is not None else '',
        'ritmo': redondear(ritmo),
        'necesita': None,
        'extra': None,
        'tono': 'verde',
        'etiqueta': '',
    }
    if limite is not None and limite > ahora:
        necesita = falta / (limite - ahora)
        salida['necesita'] = redondear(necesita)
        if necesita > ritmo:
            salida['extra'] = redondear(necesita - ritmo)
    if quieta is None or quieta >= 2:
        salida['tono'] = 'gris'
        salida['etiqueta'] = (f'Sin aportes desde {MESES_LARGOS[ultimo.fecha.month - 1]}'
                              if ultimo else 'Todavía sin aportes')
    elif limite is not None and limite <= ahora:
        salida['tono'] = 'ambar'
        salida['etiqueta'] = f'Tu fecha era {salida["limite"]}'
    elif limite is not None and llega is not None and llega > limite:
        n = llega - limite
        salida['tono'] = 'ambar'
        salida['etiqueta'] = f'{n} mes{"es" if n != 1 else ""} después de tu fecha'
    elif limite is not None:
        salida['etiqueta'] = f'A tiempo para {salida["limite"]}'
    else:
        salida['etiqueta'] = 'Sin fecha límite'
    return salida


def metas_2c(datos, hoy):
    total = sum((a_decimal(d['meta'].monto_meta or 0) for d in datos), CERO) or 1
    filas = []
    for i, d in enumerate(datos):
        filas.append({
            'd': d,
            'tono': TONOS_META[i % len(TONOS_META)],
            'eta': eta_meta(d, hoy),
            'ancho_total': _pct(float(a_decimal(d['meta'].monto_actual or 0) / total * 100)),
        })
    abiertas = [f for f in filas if f['eta'] and f['eta']['llega_indice'] is not None]
    proxima = min(abiertas, key=lambda f: f['eta']['llega_indice']) if abiertas else None
    return {
        'metas': filas,
        'este_mes': sum((a_decimal(d['serie'][-1]['monto']) for d in datos if d.get('serie')), CERO),
        'promedio': redondear(sum((a_decimal(d.get('aportado_6m') or 0) for d in datos), CERO) / 6),
        'proxima': ({'nombre': proxima['d']['meta'].nombre, 'llega': proxima['eta']['llega']}
                    if proxima else None),
    }


def barras_dobles(meses, ingresos, gastos, cuantos=6, elegido=None, hoy=None):
    filas = list(zip(meses or [], ingresos or [], gastos or [], strict=False))
    clave = str(elegido or '').strip().lower()
    fin = len(filas)
    for i, fila in enumerate(filas):
        if clave and str(fila[0]).strip().lower() == clave:
            fin = i + 1
            break
    filas = filas[max(0, fin - int(cuantos)):fin]
    tope = _techo(max([float(a_decimal(v or 0)) for _, e, g in filas for v in (e, g)] + [1.0]))
    curso = f'{MESES_LARGOS[hoy.month - 1]} {hoy.year}' if hoy else ''
    salida = []
    for i, (mes, e, g) in enumerate(filas):
        e, g = a_decimal(e or 0), a_decimal(g or 0)
        partes = str(mes).split()
        salida.append({
            'corta': partes[0][:3].capitalize() if partes else str(mes),
            'larga': partes[0].capitalize() if partes else str(mes),
            'ent': _pct(max(1.5, float(e) / tope * 100)) if e > 0 else '0',
            'sal': _pct(max(1.5, float(g) / tope * 100)) if g > 0 else '0',
            'ent_valor': e,
            'sal_valor': g,
            'neto': e - g,
            'rojo': g > e,
            'actual': i == len(filas) - 1,
            'en_curso': str(mes).strip().lower() == curso,
        })
    cerrados = [s for s in salida if not s['en_curso']]
    rojos = [s for s in cerrados if s['rojo']]
    if not cerrados:
        titulo = 'Todavía no hay meses cerrados para comparar'
    elif not rojos:
        titulo = 'Todos estos meses entró más de lo que salió'
    elif len(rojos) == 1:
        titulo = f'{rojos[0]["larga"]} fue el único mes en que salió más de lo que entró'
    else:
        titulo = f'En {len(rojos)} de los últimos {len(cerrados)} meses salió más de lo que entró'
    escala = [{'valor': Decimal(round(tope * k / 2)), 'arriba': _pct(100 - k * 50)} for k in (2, 1)]
    return {'meses': salida, 'titulo': titulo, 'escala': escala}


def _casi_igual(delta):
    try:
        return delta is not None and abs(float(delta)) < 3
    except (TypeError, ValueError):
        return False


def series_categorias(usuario, ranking, year, month):
    _, ultimo = calendar.monthrange(year, month)
    inicio = date(year, month, 1) - relativedelta(months=5)
    meses = [inicio + relativedelta(months=i) for i in range(6)]
    totales = defaultdict(dict)
    for f in (Transaccion.objects.filter(usuario=usuario, tipo='EGRESO', fecha__gte=inicio,
                                         fecha__lte=date(year, month, ultimo))
              .annotate(mes=TruncMonth('fecha')).values('mes', slug=F('categoria_ref__slug'))
              .annotate(total=Sum('monto')).order_by()):
        totales[f['slug'] or 'Otros'][(f['mes'].year, f['mes'].month)] = f['total']
    salida = []
    for fila in ranking:
        serie = [totales[fila['nombre']].get((m.year, m.month), CERO) for m in meses]
        tope = float(max(serie + [Decimal('1')]))
        salida.append({**fila, 'igual': _casi_igual(fila.get('delta')), 'spark': [
            {'alto': max(8, round(float(v) / tope * 100)) if v else 0, 'cero': not v, 'valor': v,
             'mes': MESES_LARGOS[m.month - 1].capitalize(), 'actual': i == len(serie) - 1}
            for i, (m, v) in enumerate(zip(meses, serie, strict=True))
        ]})
    return salida


def anotado_por_mes(usuario, hoy):
    inicio = date(hoy.year, hoy.month, 1) - relativedelta(months=5)
    cuenta = {
        (f['mes'].year, f['mes'].month): f['n']
        for f in Transaccion.objects.filter(usuario=usuario, fecha__gte=inicio, fecha__lte=hoy)
        .annotate(mes=TruncMonth('fecha')).values('mes').annotate(n=Count('id')).order_by()
    }
    meses = [inicio + relativedelta(months=i) for i in range(6)]
    valores = [cuenta.get((m.year, m.month), 0) for m in meses]
    tope = max(valores + [1])
    return [{'corto': MESES_LARGOS[m.month - 1][:3].capitalize(), 'n': n,
             'alto': max(4, round(n / tope * 100)) if n else 3, 'actual': i == len(meses) - 1}
            for i, (m, n) in enumerate(zip(meses, valores, strict=True))]


def flujo(ingreso, gasto, cuotas):
    ingreso, gasto, cuotas = (max(CERO, a_decimal(v or 0)) for v in (ingreso, gasto, cuotas))
    sale = gasto + cuotas
    escala = max(ingreso, sale)
    if ingreso <= 0 or escala <= 0:
        return None
    sobra = max(CERO, ingreso - sale)

    def ancho(valor):
        return _pct(float(valor / escala * 100))

    def de_ingreso(valor):
        return redondear(valor / ingreso * 100)

    return {
        'gasto': ancho(gasto),
        'cuotas': ancho(cuotas) if cuotas > 0 else None,
        'sobra': ancho(sobra) if sobra > 0 else None,
        'marca': ancho(ingreso) if sale > ingreso else None,
        'pct_gasto': de_ingreso(gasto),
        'pct_cuotas': de_ingreso(cuotas),
        'pct_sobra': de_ingreso(sobra),
        'pct_sale': de_ingreso(sale),
        'pasa': sale > ingreso,
    }
