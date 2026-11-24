import calendar
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction
from django.db.models import Q

from ..models import IngresoFijo, IngresoMes, Transaccion
from ..models.ingresos import nombre_periodo, periodo_de, sumar_meses
from .mes import invalidar

CERO = Decimal('0')
DESDE, HASTA = Decimal('0.7'), Decimal('1.6')
INICIALES = 'EFMAMJJASOND'
DIAS = ((1, 'Día 1'), (5, 'Día 5'), (15, 'Día 15'), (25, 'Día 25'), (30, 'Día 30'),
        (IngresoFijo.ULTIMO_HABIL, 'Último día hábil'))
TEXTOS = {
    'antes': 'antes de tu sueldo',
    'recibido': 'recibido',
    'extra': 'recibido con horas extra',
    'sin_confirmar': 'sin confirmar',
    'por_recibir': 'por recibir',
    'futuro': 'todavía no llega',
}


def de(usuario):
    return IngresoFijo.objects.filter(usuario=usuario).first()


def _filas(ingreso):
    return {f.periodo: f for f in ingreso.meses.all()}


def sueldo_de(ingreso, fila):
    if fila is not None and fila.monto is not None:
        return fila.monto
    return ingreso.monto


def esperado_de(ingreso, fila):
    return sueldo_de(ingreso, fila) + (fila.extra if fila is not None else CERO)


def _llego(fila):
    return fila is not None and fila.llego


def mes(ingreso, periodo, fila, hoy):
    actual = periodo_de(hoy)
    sueldo = sueldo_de(ingreso, fila)
    extra = fila.extra if fila is not None else CERO
    esperado = sueldo + extra
    llego = _llego(fila)
    recibido = fila.monto_recibido if llego and fila.monto_recibido is not None else None
    otro = recibido - esperado if recibido is not None and recibido != esperado else None
    if periodo < ingreso.inicio:
        estado = 'antes'
    elif llego:
        estado = 'extra' if extra > 0 else 'recibido'
    elif periodo < actual:
        estado = 'sin_confirmar'
    elif periodo == actual:
        estado = 'por_recibir'
    else:
        estado = 'futuro'
    return {
        'periodo': periodo,
        'valor': f'{periodo // 100}-{periodo % 100:02d}',
        'nombre': nombre_periodo(periodo),
        'inicial': INICIALES[periodo % 100 - 1],
        'sueldo': sueldo,
        'extra': extra,
        'nota': fila.nota if fila is not None else '',
        'esperado': esperado,
        'total': recibido if recibido is not None else esperado,
        'otro': otro,
        'otro_abs': abs(otro) if otro is not None else None,
        'cambiado': fila is not None and fila.monto is not None and fila.monto != ingreso.monto,
        'estado': estado,
        'texto': TEXTOS[estado],
        'recibido': fila.recibido if llego else None,
        'por_cartola': llego and fila.por_cartola,
        'fecha_pago': ingreso.fecha_pago(periodo),
        'es_actual': periodo == actual,
        'puede_llegar': estado in ('por_recibir', 'sin_confirmar'),
        'elegible': ingreso.inicio <= periodo <= actual,
    }


def _tarjeta(ingreso, filas, hoy):
    actual = periodo_de(hoy)
    este = mes(ingreso, actual, filas.get(actual), hoy)
    llega = este['fecha_pago']
    if este['recibido']:
        objetivo = sumar_meses(actual, 1)
        cartola = ' · por la cartola' if este['por_cartola'] else ''
        titulo, detalle = 'recibido', f'Llegó el {este["recibido"].day}{cartola}'
    elif llega < hoy:
        objetivo = actual
        titulo, detalle = 'sin confirmar', f'Debía llegar el {llega.day} · márcalo cuando llegue'
    else:
        objetivo = actual
        titulo, detalle = 'por recibir', f'Llega el {llega.day} · la cartola lo marca sola'
    fin = ingreso.fecha_pago(objetivo)
    previo = ingreso.fecha_pago(sumar_meses(objetivo, -1))
    dias = max(0, (fin - hoy).days)
    ciclo = max(1, (fin - previo).days)
    pct = max(0, min(100, round((hoy - previo).days * 100 / ciclo)))
    if fin < hoy:
        numero, unidad = str((hoy - fin).days), 'tarde'
    elif dias == 0:
        numero, unidad = '0', 'hoy'
    else:
        numero, unidad = str(dias), 'día' if dias == 1 else 'días'
    destino = nombre_periodo(objetivo)
    if fin < hoy:
        lectura = f'Tu sueldo de {destino} debía llegar el {fin.day}'
    elif dias == 0:
        lectura = f'Tu sueldo de {destino} llega hoy'
    else:
        lectura = f'Faltan {dias} {unidad} para tu sueldo de {destino}'
    return {'mes': este, 'titulo': titulo, 'detalle': detalle, 'numero': numero, 'unidad': unidad,
            'pct': 100 if fin < hoy else pct, 'tarde': fin < hoy, 'lectura': lectura}


def pantalla(usuario, elegido, hoy):
    ingreso = de(usuario)
    actual = periodo_de(hoy)
    base = {'dias': DIAS, 'mes_actual': nombre_periodo(actual)}
    if ingreso is None:
        return {**base, 'ingreso': None, 'dia_elegido': 30, 'dia_otro': ''}
    filas = _filas(ingreso)
    year = elegido // 100
    meses = []
    for m in range(1, 13):
        periodo = year * 100 + m
        dato = mes(ingreso, periodo, filas.get(periodo), hoy)
        dato['elegido'] = periodo == elegido
        meses.append(dato)
    recibidos = [m for m in meses if m['recibido']]
    detalle = mes(ingreso, elegido, filas.get(elegido), hoy)
    fijos = {valor for valor, _ in DIAS}
    return {
        **base,
        'ingreso': ingreso,
        'tarjeta': _tarjeta(ingreso, filas, hoy),
        'anio': year,
        'meses': meses,
        'llevas': sum((m['total'] for m in recibidos), CERO),
        'extras': sum((m['extra'] for m in recibidos), CERO),
        'hay_sin_confirmar': any(m['estado'] == 'sin_confirmar' for m in meses),
        'detalle': detalle,
        'inicio_nombre': nombre_periodo(ingreso.inicio),
        'dia_elegido': ingreso.dia_pago if ingreso.dia_pago in fijos else '',
        'dia_otro': '' if ingreso.dia_pago in fijos else ingreso.dia_pago,
    }


def _ventana(ingreso, periodo):
    year, month = divmod(periodo, 100)
    desde = date(year, month, 1)
    hasta = date(year, month, calendar.monthrange(year, month)[1])
    if ingreso.paga_temprano:
        desde -= timedelta(days=3)
    if ingreso.paga_tarde:
        hasta += timedelta(days=3)
    return desde, hasta


def _existente(ingreso, periodo, esperado):
    desde, hasta = _ventana(ingreso, periodo)
    candidatos = (Transaccion.objects
                  .filter(usuario_id=ingreso.usuario_id, tipo='INGRESO', fecha__range=(desde, hasta),
                          ingreso_mes__isnull=True, monto__gte=esperado * DESDE, monto__lte=esperado * HASTA)
                  .filter(Q(categoria_ref__slug='Sueldo') | Q(monto=esperado)))
    return min(candidatos, key=lambda t: (abs(t.monto - esperado), t.fecha), default=None)


def _vincular(fila, tx, propio):
    fila.recibido = tx.fecha
    fila.monto_recibido = tx.monto
    fila.por_cartola = tx.origen == Transaccion.CARTOLA
    fila.anotado_aqui = propio
    fila.transaccion = tx
    fila.save()


def _fila(ingreso, periodo):
    fila, _ = IngresoMes.objects.select_for_update().get_or_create(ingreso=ingreso, periodo=periodo)
    return fila


def guardar(usuario, nombre, monto, dia, hoy):
    actual = periodo_de(hoy)
    with db_transaction.atomic():
        ingreso = IngresoFijo.objects.select_for_update().filter(usuario=usuario).first()
        if ingreso is None:
            ingreso = IngresoFijo.objects.create(usuario=usuario, nombre=nombre, monto=monto, dia_pago=dia,
                                                 inicio=actual)
            tx = _existente(ingreso, actual, monto)
            if tx is not None:
                _vincular(IngresoMes(ingreso=ingreso, periodo=actual), tx, False)
            nuevo = True
        else:
            ingreso.nombre, ingreso.dia_pago = nombre, dia
            ingreso.save(update_fields=['nombre', 'dia_pago'])
            if monto != ingreso.monto:
                _cambiar(ingreso, max(actual, ingreso.inicio), monto, True, False)
            nuevo = False
    invalidar(usuario.pk)
    return nuevo


def llego(ingreso, periodo, hoy):
    with db_transaction.atomic():
        fila = _fila(ingreso, periodo)
        if fila.llego:
            return None
        esperado = esperado_de(ingreso, fila)
        tx = _existente(ingreso, periodo, esperado)
        propio = tx is None
        if propio:
            fecha = hoy if periodo == periodo_de(hoy) else min(ingreso.fecha_pago(periodo), hoy)
            tx = Transaccion.objects.create(usuario_id=ingreso.usuario_id, tipo='INGRESO', monto=esperado,
                                            categoria='Sueldo', fecha=fecha, descripcion=ingreso.descripcion,
                                            pagado=True, fecha_pago=fecha)
        _vincular(fila, tx, propio)
    invalidar(ingreso.usuario_id)
    return fila


def deshacer(ingreso, periodo):
    with db_transaction.atomic():
        fila = IngresoMes.objects.select_for_update().filter(ingreso=ingreso, periodo=periodo).first()
        if fila is None or fila.recibido is None:
            return False
        tx = fila.transaccion if fila.anotado_aqui else None
        fila.recibido = None
        fila.monto_recibido = None
        fila.por_cartola = False
        fila.anotado_aqui = False
        fila.transaccion = None
        fila.save()
        if tx is not None:
            tx.delete()
    invalidar(ingreso.usuario_id)
    return True


def _al_dia(ingreso, fila):
    if not (fila.llego and fila.anotado_aqui):
        return
    total = esperado_de(ingreso, fila)
    Transaccion.objects.filter(pk=fila.transaccion_id).update(monto=total)
    fila.monto_recibido = total
    fila.save(update_fields=['monto_recibido'])


def ajustar_extra(ingreso, periodo, extra, nota):
    with db_transaction.atomic():
        fila = _fila(ingreso, periodo)
        fila.extra = extra
        fila.nota = nota[:80] if extra > 0 else ''
        fila.save(update_fields=['extra', 'nota'])
        _al_dia(ingreso, fila)
    invalidar(ingreso.usuario_id)


def _cambiar(ingreso, periodo, nuevo, adelante, limpiar):
    if adelante:
        filas = _filas(ingreso)
        p = ingreso.inicio
        while p < periodo:
            fila = filas.get(p) or IngresoMes(ingreso=ingreso, periodo=p)
            if fila.monto is None:
                fila.monto = ingreso.monto
                fila.save()
            p = sumar_meses(p, 1)
        ingreso.monto = nuevo
        ingreso.save(update_fields=['monto'])
        IngresoMes.objects.filter(ingreso=ingreso, periodo__gte=periodo).update(monto=None)
    fila = _fila(ingreso, periodo)
    if not adelante:
        fila.monto = None if nuevo == ingreso.monto else nuevo
    if limpiar:
        fila.extra = CERO
        fila.nota = ''
    fila.save()
    _al_dia(ingreso, fila)
    if adelante:
        for otra in IngresoMes.objects.filter(ingreso=ingreso, periodo__gt=periodo, anotado_aqui=True,
                                              transaccion__isnull=False):
            _al_dia(ingreso, otra)


def cambiar_monto(ingreso, periodo, nuevo, adelante):
    with db_transaction.atomic():
        ingreso = IngresoFijo.objects.select_for_update().get(pk=ingreso.pk)
        _cambiar(ingreso, periodo, nuevo, adelante, True)
    invalidar(ingreso.usuario_id)


def quitar(usuario):
    borrados, _ = IngresoFijo.objects.filter(usuario=usuario).delete()
    invalidar(usuario.pk)
    return borrados > 0


def periodo_de_fecha(ingreso, fecha):
    periodo = periodo_de(fecha)
    ultimo = calendar.monthrange(fecha.year, fecha.month)[1]
    if ingreso.paga_tarde and fecha.day <= 3:
        return sumar_meses(periodo, -1)
    if ingreso.paga_temprano and fecha.day > ultimo - 3:
        return sumar_meses(periodo, 1)
    return periodo


def _palabras(texto):
    return {w for w in re.findall(r'[a-z0-9áéíóúñü]+', (texto or '').lower()) if len(w) >= 4}


def en_cartola(usuario, movimientos, hoy):
    ingreso = de(usuario)
    if ingreso is None:
        return {}
    filas = _filas(ingreso)
    actual = periodo_de(hoy)
    nombre = _palabras(ingreso.nombre)
    elegidos = {}
    for i, m in enumerate(movimientos):
        if m.get('tipo') != 'INGRESO' or m.get('ya_existe'):
            continue
        try:
            fecha = date.fromisoformat(m['fecha'])
            monto = Decimal(str(m['monto']))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
        periodo = periodo_de_fecha(ingreso, fecha)
        if not ingreso.inicio <= periodo <= actual:
            continue
        fila = filas.get(periodo)
        if _llego(fila) and fila.por_cartola:
            continue
        esperado = esperado_de(ingreso, fila)
        exacto = monto == esperado
        parecido = m.get('categoria') == 'Sueldo' or bool(nombre & _palabras(m.get('descripcion')))
        if not exacto and not (parecido and esperado * DESDE <= monto <= esperado * HASTA):
            continue
        clave = (0 if exacto else 1, abs(monto - esperado))
        if periodo not in elegidos or clave < elegidos[periodo][0]:
            elegidos[periodo] = (clave, i, monto, esperado, fila)
    salida = {}
    for periodo, (_, i, monto, esperado, fila) in elegidos.items():
        diferencia = monto - esperado
        salida[i] = {
            'periodo': periodo,
            'mes': nombre_periodo(periodo),
            'esperado': esperado,
            'diferencia': diferencia,
            'mas': diferencia if diferencia > 0 else CERO,
            'menos': -diferencia if diferencia < 0 else CERO,
            'a_mano': bool(_llego(fila) and not fila.por_cartola),
        }
    return salida


def recibir_por_cartola(usuario, info, monto, fecha, descripcion, categoria, con_extra, tx=None):
    ingreso = de(usuario)
    if ingreso is None:
        return None
    fila = _fila(ingreso, info['periodo'])
    if tx is None:
        tx = fila.transaccion if fila.llego else None
        if tx is None:
            return None
        tx.fecha = fecha
        tx.fecha_pago = fecha
        tx.monto = monto
        tx.descripcion = descripcion
        tx.categoria = categoria
        tx.pagado = True
        tx.origen = Transaccion.CARTOLA
        tx.save()
    base = sueldo_de(ingreso, fila)
    if con_extra and monto > base:
        fila.extra = monto - base
        fila.nota = fila.nota or 'Llegó en la cartola'
    fila.recibido = fecha
    fila.monto_recibido = monto
    fila.por_cartola = True
    fila.anotado_aqui = False
    fila.transaccion = tx
    fila.save()
    return fila
