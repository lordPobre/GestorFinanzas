from decimal import Decimal

from dateutil.relativedelta import relativedelta

from ..servicios.repetidos import MINIMO, parecido

HOLGURA_MESES = 2
HOLGURA_MONTO = Decimal('0.02')
HOLGURA_MINIMA = Decimal('10')
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre')


def _periodo(fecha):
    return fecha.year * 100 + fecha.month


def _meses_entre(a, b):
    return abs((a // 100 - b // 100) * 12 + a % 100 - b % 100)


def _mes(periodo):
    return f'{MESES[periodo % 100 - 1]} {periodo // 100}'


def calza_monto(monto, esperado):
    return abs(monto - esperado) <= max(HOLGURA_MINIMA, abs(esperado) * HOLGURA_MONTO)


def indice_de_la_cuota(periodos, actual, total, fecha):
    corrimiento = total - len(periodos)
    indice = actual - corrimiento - 1
    if corrimiento < 0 or not 0 <= indice < len(periodos):
        return None
    if _meses_entre(periodos[indice], _periodo(fecha)) > HOLGURA_MESES:
        return None
    return indice


def _periodos_prestamo(prestamo):
    return [_periodo(prestamo.fecha + relativedelta(months=i)) for i in range(prestamo.cuotas_totales)]


def _cuota_prestamo(prestamo, indice):
    if indice == prestamo.cuotas_totales - 1:
        return Decimal(prestamo.monto) - prestamo.monto_cuota * (prestamo.cuotas_totales - 1)
    return prestamo.monto_cuota


def _opciones(m, deudas, pagos, prestamos, tomadas):
    salida = []
    for d in deudas:
        periodos = d.periodos_programados
        indice = indice_de_la_cuota(periodos, m.cuota_actual, m.cuota_total, m.fecha)
        if indice is None or ('deuda', d.pk, periodos[indice]) in tomadas:
            continue
        pago = pagos[d.pk].get(periodos[indice])
        esperado = Decimal(pago.monto) if pago else d.monto_cuota_de(periodos[indice])
        if calza_monto(m.monto, esperado):
            salida.append(('deuda', d, periodos[indice], parecido(m.descripcion, d.acreedor),
                           abs(m.monto - esperado)))
    for p in prestamos:
        periodos = _periodos_prestamo(p)
        indice = indice_de_la_cuota(periodos, m.cuota_actual, m.cuota_total, m.fecha)
        if indice is None or ('prestamo', p.pk, periodos[indice]) in tomadas:
            continue
        esperado = _cuota_prestamo(p, indice)
        if calza_monto(m.monto, esperado):
            salida.append(('prestamo', p, periodos[indice], parecido(m.descripcion, p.descripcion),
                           abs(m.monto - esperado)))
    return salida


def _proponer_reemplazo(m, tx, deuda, periodo, seguro):
    m.reemplaza_id = tx.pk
    m.reemplaza_seguro = seguro
    m.reemplaza_desc = (tx.descripcion or deuda.acreedor)[:60]
    m.reemplaza_fecha = tx.fecha.strftime('%d/%m')
    if not m.aviso:
        m.aviso = (f'Ya pagaste la cuota de {_mes(periodo)} de «{deuda.acreedor}». Al guardar se '
                   f'reemplaza con la fecha y la descripción del banco.')


def reconocer_cuotas(cartola, usuario):
    from ..models import Deuda, Prestamo

    filas = [m for m in cartola.movimientos
             if m.es_cuota and m.tipo == 'EGRESO' and not m.ya_existe and not m.mover_id]
    if not filas:
        return cartola

    deudas = list(Deuda.objects.filter(usuario=usuario).select_related('categoria_ref')
                  .prefetch_related('pagos__transaccion'))
    prestamos = list(Prestamo.objects.filter(persona__usuario=usuario, persona__lado='ME_DEBE',
                                             tipo='CUOTAS').select_related('persona'))
    if not deudas and not prestamos:
        return cartola
    pagos = {d.pk: {p.periodo: p for p in d.pagos.all()} for d in deudas}
    tomadas = set()

    for m in filas:
        opciones = _opciones(m, deudas, pagos, prestamos, tomadas)
        if not opciones:
            continue
        clase, cosa, periodo, nombre, diferencia = max(opciones, key=lambda o: (o[3], -o[4]))
        seguro = nombre >= MINIMO or (len(opciones) == 1 and diferencia == 0)
        tomadas.add((clase, cosa.pk, periodo))

        if clase == 'prestamo':
            m.prestamo_id = cosa.pk
            m.prestamo_texto = (f'Es «{cosa.descripcion}», que te debe {cosa.persona.nombre}'
                                f' · ya está en Préstamos')
            m.vinculo_seguro = seguro
            continue

        pago = pagos[cosa.pk].get(periodo)
        if pago is not None and pago.transaccion_id:
            _proponer_reemplazo(m, pago.transaccion, cosa, periodo, seguro)
            continue

        m.deuda_id = cosa.pk
        m.deuda_periodo = periodo
        m.deuda_texto = f'Es «{cosa.acreedor}» de Cuotas · marcar pagada la de {_mes(periodo)}'
        m.vinculo_seguro = seguro
        m.categoria = cosa.categoria
    return cartola
