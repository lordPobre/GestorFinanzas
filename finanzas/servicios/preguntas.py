import calendar
import math
import unicodedata
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Sum

from .. import fechas
from ..dinero import a_decimal, redondear, suma
from ..models import Categoria, Deuda, MetaAhorro, Prestamo, Transaccion
from ..templatetags.moneda import SIN_DECIMALES
from .mes import nombre_mes_es, resumen_mes
from .proyeccion import MAX_MESES, proyeccion

MAX_MONTO = a_decimal('999999999')
MESES_POR_DEFECTO = 6

HERRAMIENTAS = [
    {
        'name': 'simular_compra',
        'description': ('Simula una compra nueva sobre la proyección de los próximos meses. Devuelve si alcanza, '
                        'la cuota, el mes más justo y lo que quedaría libre cada mes. Una compra en cuotas '
                        'empieza a cobrarse el mes siguiente; al contado, este mes.'),
        'input_schema': {
            'type': 'object',
            'properties': {
                'monto': {'type': 'number', 'description': 'Precio total de la compra.'},
                'cuotas': {'type': 'integer', 'description': 'Número de cuotas, 1 si es al contado.'},
            },
            'required': ['monto'],
        },
    },
    {
        'name': 'queda_mes',
        'description': 'Cuánto le queda para gastar este mes, cuánto lleva gastado y cuánto le falta pagar.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'gasto_categoria',
        'description': ('Cuánto gastó en una categoría en un mes, comparado con el mes anterior. Si la categoría '
                        'no existe, devuelve la lista de categorías disponibles.'),
        'input_schema': {
            'type': 'object',
            'properties': {
                'categoria': {'type': 'string', 'description': 'Nombre de la categoría, por ejemplo comida.'},
                'meses_atras': {'type': 'integer', 'description': '0 para este mes, 1 para el mes pasado.'},
            },
            'required': ['categoria'],
        },
    },
    {
        'name': 'fin_deuda',
        'description': ('Las compras en cuotas y los préstamos que debe, con lo que falta, la cuota y el mes en '
                        'que termina. Los nombres vienen como alias; úsalos tal cual en la respuesta.'),
        'input_schema': {
            'type': 'object',
            'properties': {
                'nombre': {'type': 'string', 'description': 'Parte del nombre de la deuda, si la nombró.'},
            },
        },
    },
    {
        'name': 'cuotas_por_mes',
        'description': ('Cuánto paga en cuotas cada mes, sumando las compras en cuotas y los préstamos en cuotas '
                        'que debe. Devuelve el total de cada mes con su detalle, el total del período, el mes '
                        'más cargado, lo atrasado de meses anteriores y el total de todas las cuotas que faltan. '
                        'Los nombres vienen como alias; úsalos tal cual.'),
        'input_schema': {
            'type': 'object',
            'properties': {
                'meses': {'type': 'integer',
                          'description': f'Cuántos meses sumar, de 1 a {MAX_MESES}. Si no lo dijo, 6.'},
                'desde_el_proximo': {'type': 'boolean',
                                     'description': 'true si pregunta por los meses que vienen sin contar este.'},
            },
        },
    },
    {
        'name': 'metas',
        'description': 'Cómo van sus metas de ahorro. Los nombres vienen como alias; úsalos tal cual.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
]


class ErrorHerramienta(ValueError):
    pass


def _simple(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode()
    return ' '.join(texto.lower().split())


def _monto(valor, simbolo):
    if simbolo in SIN_DECIMALES:
        return redondear(valor)
    return str(redondear(valor, 2))


def _alias(alias, prefijo, nombre):
    for clave, real in alias.items():
        if real == nombre and clave.startswith(prefijo):
            return clave
    clave = f'{prefijo} {sum(1 for c in alias if c.startswith(prefijo)) + 1}'
    alias[clave] = nombre
    return clave


def _etiqueta(periodo):
    return nombre_mes_es(periodo // 100, periodo % 100, capitalizado=False)


def _periodo(f):
    return f.year * 100 + f.month


def _prestamos_que_debo(usuario):
    return (Prestamo.objects.filter(persona__usuario=usuario, persona__lado='LE_DEBO')
            .select_related('persona').prefetch_related('abonos'))


def simular_compra(usuario, simbolo, alias, monto=None, cuotas=1):
    try:
        monto = a_decimal(monto)
        cuotas = int(cuotas or 1)
    except (ArithmeticError, TypeError, ValueError):
        raise ErrorHerramienta('monto o cuotas no válidos') from None
    if monto <= 0 or monto > MAX_MONTO or not 1 <= cuotas <= MAX_MESES:
        raise ErrorHerramienta(f'el monto debe ser positivo y las cuotas entre 1 y {MAX_MESES}')
    p = proyeccion(usuario, compra={'monto': monto, 'cuotas': cuotas})
    con_compra = [m for m in p['meses'] if any(c['tipo'] == 'compra' for c in m['cobros'])]
    cuota = next(c['monto'] for c in con_compra[0]['cobros'] if c['tipo'] == 'compra')
    justo = next(m for m in p['meses'] if m['periodo'] == p['mas_justo'])
    return {
        'alcanza': p['alcanza'],
        'cuotas': cuotas,
        'cuota': _monto(cuota, simbolo),
        'desde': _etiqueta(con_compra[0]['periodo']),
        'hasta': _etiqueta(con_compra[-1]['periodo']),
        'mes_mas_justo': justo['etiqueta'],
        'libre_mes_mas_justo': _monto(justo['libre'], simbolo),
        'meses': [{'mes': m['etiqueta'], 'libre': _monto(m['libre'], simbolo)} for m in p['meses']],
        'pocos_datos': p['base']['meses_base'] < 2,
    }


def queda_mes(usuario, simbolo, alias):
    hoy = fechas.hoy()
    r = resumen_mes(usuario, hoy.year, hoy.month)
    return {
        'mes': nombre_mes_es(hoy.year, hoy.month, capitalizado=False),
        'puedes_gastar': _monto(r['disponible'], simbolo),
        'entro': _monto(r['ingresos'], simbolo),
        'gastado': _monto(r['gastos'] + r['total_cuotas_mes'], simbolo),
        'falta_pagar': _monto(r['cuotas_pendientes_mes'] + r['servicios_pendientes_mes']
                              + r['debo_pendiente_mes'], simbolo),
        'dias_restantes': r['dias_restantes'],
        'por_dia': _monto(r['por_dia'], simbolo),
    }


def _gastado(usuario, slug, year, month):
    _, ultimo = calendar.monthrange(year, month)
    return Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO', categoria_ref__slug=slug,
        fecha__gte=date(year, month, 1), fecha__lte=date(year, month, ultimo),
    ).aggregate(total=Sum('monto'), n=Count('pk'))


def gasto_categoria(usuario, simbolo, alias, categoria='', meses_atras=0):
    try:
        meses_atras = max(0, min(11, int(meses_atras or 0)))
    except (TypeError, ValueError):
        raise ErrorHerramienta('meses_atras no válido') from None
    buscado = _simple(categoria)
    if not buscado:
        raise ErrorHerramienta('falta la categoría')
    mapa = Categoria.mapa(usuario)
    opciones = {slug: datos.get('label', slug) for slug, datos in mapa.items()}
    slug = next((s for s, l in opciones.items() if buscado in (_simple(s), _simple(l))), None)
    slug = slug or next((s for s, l in opciones.items() if buscado in _simple(l) or _simple(l) in buscado), None)
    if slug is None:
        return {'encontrada': False, 'categorias': sorted(set(opciones.values()))}
    hoy = fechas.hoy()
    f = date(hoy.year, hoy.month, 1) - relativedelta(months=meses_atras)
    antes = f - relativedelta(months=1)
    ahora = _gastado(usuario, slug, f.year, f.month)
    previo = _gastado(usuario, slug, antes.year, antes.month)
    return {
        'encontrada': True,
        'categoria': opciones[slug],
        'mes': nombre_mes_es(f.year, f.month, capitalizado=False),
        'total': _monto(ahora['total'], simbolo),
        'movimientos': ahora['n'],
        'mes_anterior': nombre_mes_es(antes.year, antes.month, capitalizado=False),
        'total_mes_anterior': _monto(previo['total'], simbolo),
    }


def fin_deuda(usuario, simbolo, alias, nombre=''):
    hoy = fechas.hoy()
    buscado = _simple(nombre)
    filas = []
    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        pendientes = d.periodos_pendientes
        if d.esta_saldada or not pendientes:
            continue
        filas.append((d.acreedor, {
            'tipo': 'compra en cuotas',
            'falta': _monto(d.monto_restante, simbolo),
            'cuota': _monto(d.monto_cuota, simbolo),
            'cuotas_que_faltan': len(pendientes),
            'termina': _etiqueta(pendientes[-1]),
        }))
    for pr in _prestamos_que_debo(usuario):
        if pr.esta_pagado:
            continue
        fila = {'tipo': 'préstamo que debes', 'falta': _monto(pr.monto_pendiente, simbolo)}
        if pr.tipo == 'CUOTAS' and pr.monto_cuota > 0:
            n = math.ceil(pr.monto_pendiente / pr.monto_cuota)
            desde = 0 if pr.falta_este_mes(hoy.year, hoy.month) > 0 else 1
            fin = date(hoy.year, hoy.month, 1) + relativedelta(months=desde + n - 1)
            fila.update({'cuota': _monto(pr.monto_cuota, simbolo), 'cuotas_que_faltan': n,
                         'termina': nombre_mes_es(fin.year, fin.month, capitalizado=False)})
        else:
            fila['termina'] = 'sin fecha'
        filas.append((f'{pr.persona.nombre} {pr.descripcion}', fila))
    if buscado:
        elegidas = [f for f in filas if buscado in _simple(f[0]) or _simple(f[0]) in buscado]
        filas = elegidas or filas
    salida = [{'nombre': _alias(alias, 'Deuda', real), **datos} for real, datos in filas]
    return {'deudas': salida, 'total_falta': _monto(suma(a_decimal(str(d['falta'])) for d in salida), simbolo)}


def cuotas_por_mes(usuario, simbolo, alias, meses=MESES_POR_DEFECTO, desde_el_proximo=False):
    try:
        meses = MESES_POR_DEFECTO if meses is None else int(meses)
    except (TypeError, ValueError):
        raise ErrorHerramienta('meses no válido') from None
    if not 1 <= meses <= MAX_MESES:
        raise ErrorHerramienta(f'meses debe estar entre 1 y {MAX_MESES}')

    hoy = fechas.hoy()
    primero = date(hoy.year, hoy.month, 1)
    actual = _periodo(primero)
    cero = a_decimal(0)
    por_mes = {}
    atrasado = cero
    sin_fecha = cero
    total = cero

    def anotar(periodo, nombre, monto):
        detalle = por_mes.setdefault(periodo, {})
        detalle[nombre] = detalle.get(nombre, cero) + monto

    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        pendientes = d.periodos_pendientes
        if d.esta_saldada or not pendientes:
            continue
        nombre = _alias(alias, 'Deuda', d.acreedor)
        for p in pendientes:
            monto = a_decimal(d.monto_cuota_de(p))
            total += monto
            if p < actual:
                atrasado += monto
            else:
                anotar(p, nombre, monto)

    for pr in _prestamos_que_debo(usuario):
        if pr.esta_pagado:
            continue
        pendiente = a_decimal(pr.monto_pendiente)
        total += pendiente
        nombre = _alias(alias, 'Deuda', f'{pr.persona.nombre} {pr.descripcion}')
        if pr.tipo != 'CUOTAS' or pr.monto_cuota <= 0:
            sin_fecha += pendiente
            continue
        cuota = a_decimal(pr.monto_cuota)
        monto = min(pendiente, a_decimal(pr.falta_este_mes(hoy.year, hoy.month)))
        i = 0
        while pendiente > 0:
            if monto > 0:
                anotar(_periodo(primero + relativedelta(months=i)), nombre, monto)
                pendiente -= monto
            i += 1
            monto = min(cuota, pendiente)

    inicio = 1 if desde_el_proximo else 0
    filas = []
    for i in range(inicio, inicio + meses):
        periodo = _periodo(primero + relativedelta(months=i))
        detalle = por_mes.get(periodo, {})
        filas.append((periodo, suma(detalle.values()), detalle))

    cargado = max(filas, key=lambda f: f[1])
    return {
        'desde': _etiqueta(filas[0][0]),
        'hasta': _etiqueta(filas[-1][0]),
        'meses': [{'mes': _etiqueta(p), 'total': _monto(t, simbolo),
                   'detalle': [{'nombre': n, 'cuota': _monto(m, simbolo)} for n, m in detalle.items()]}
                  for p, t, detalle in filas],
        'total_periodo': _monto(suma(t for _, t, _ in filas), simbolo),
        'mes_mas_cargado': _etiqueta(cargado[0]) if cargado[1] > 0 else None,
        'atrasado': _monto(atrasado, simbolo),
        'prestamos_sin_fecha': _monto(sin_fecha, simbolo),
        'total_todas_las_cuotas': _monto(total, simbolo),
    }


def metas(usuario, simbolo, alias):
    hoy = fechas.hoy()
    salida = []
    for m in MetaAhorro.objects.filter(usuario=usuario):
        falta = max(a_decimal(0), a_decimal(m.monto_meta) - a_decimal(m.monto_actual))
        salida.append({
            'nombre': _alias(alias, 'Meta', m.nombre),
            'ahorrado': _monto(m.monto_actual, simbolo),
            'objetivo': _monto(m.monto_meta, simbolo),
            'porcentaje': min(100, redondear(a_decimal(m.monto_actual) / a_decimal(m.monto_meta) * 100))
            if a_decimal(m.monto_meta) > 0 else 0,
            'falta': _monto(falta, simbolo),
            'fecha_limite': m.fecha_limite.isoformat() if m.fecha_limite else None,
            'vencida': bool(m.fecha_limite and m.fecha_limite < hoy and falta > 0),
        })
    return {'metas': salida}


FUNCIONES = {
    'simular_compra': simular_compra,
    'queda_mes': queda_mes,
    'gasto_categoria': gasto_categoria,
    'fin_deuda': fin_deuda,
    'cuotas_por_mes': cuotas_por_mes,
    'metas': metas,
}
PERMITIDOS = {h['name']: set(h['input_schema'].get('properties', {})) for h in HERRAMIENTAS}


def ejecutar(usuario, nombre, argumentos, alias, simbolo='$'):
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        return {'error': f'no existe la herramienta {nombre}'}
    argumentos = {k: v for k, v in (argumentos or {}).items() if k in PERMITIDOS[nombre]}
    try:
        return funcion(usuario, simbolo, alias, **argumentos)
    except ErrorHerramienta as e:
        return {'error': str(e)}


def restaurar(texto, alias):
    for clave in sorted(alias, key=len, reverse=True):
        texto = texto.replace(clave, alias[clave])
    return texto
