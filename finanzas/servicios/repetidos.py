import re
import unicodedata
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher

DIAS = 3
SEGURO = 0.9
MINIMO = 0.45
MAX_DUDOSOS = 60

RUIDO = {
    'compra', 'compras', 'pago', 'pagos', 'redcompra', 'pac', 'pat', 'internet', 'web',
    'chl', 'cl', 'spa', 'ltda', 'sa', 'de', 'del', 'la', 'el', 'los', 'las', 'en', 'y',
    'cuota', 'cuotas', 'pendiente', 'suscripcion', 'tef', 'transf', 'nacional', 'santiago',
}
CUOTA = re.compile(r'cuota\s+(\d{1,2})\s+de\s+(\d{1,2})', re.I)


def normalizar(desc):
    t = unicodedata.normalize('NFKD', desc or '').encode('ascii', 'ignore').decode().lower()
    t = CUOTA.sub(' ', t)
    t = re.sub(r'[^a-z ]+', ' ', t)
    return ' '.join(p for p in t.split() if len(p) > 1 and p not in RUIDO)


def parecido(a, b):
    na, nb = normalizar(a), normalizar(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    sa, sb = set(na.split()), set(nb.split())
    jaccard = len(sa & sb) / len(sa | sb)
    contiene = 0.85 if (na in nb or nb in na) else 0.0
    return max(SequenceMatcher(None, na, nb).ratio(), jaccard, contiene)


def clasificar(a, b):
    ca, cb = CUOTA.search(a['descripcion'] or ''), CUOTA.search(b['descripcion'] or '')
    if ca and cb and ca.groups() != cb.groups():
        return None
    dias = abs((a['fecha'] - b['fecha']).days)
    if dias > DIAS:
        return None
    p = parecido(a['descripcion'], b['descripcion'])
    if p >= 0.97 or (p >= SEGURO and dias <= 1):
        return 'seguro'
    vacia = not normalizar(a['descripcion']) or not normalizar(b['descripcion'])
    misma_categoria = a['categoria'] == b['categoria'] and a['categoria'] not in ('Otros', 'Otros_Ingresos')
    if p >= MINIMO or vacia or misma_categoria:
        return 'dudoso'
    return None


def _datos_tx(t):
    return {'fecha': t.fecha, 'monto': Decimal(t.monto), 'tipo': t.tipo,
            'categoria': t.categoria, 'descripcion': t.descripcion or ''}


def _datos_mov(m):
    return {'fecha': m.fecha, 'monto': m.monto, 'tipo': m.tipo,
            'categoria': m.categoria, 'descripcion': m.descripcion}


def puede_usar_ia(usuario):
    from .. import legal
    perfil = getattr(usuario, 'profile', None)
    return bool(perfil and perfil.analisis_ia and perfil.politica_version == legal.VERSION)


def _consultar(pares, usuario):
    if not pares or not puede_usar_ia(usuario):
        return {}
    from ..ia_repetidos import revisar_pares
    return revisar_pares(pares[:MAX_DUDOSOS])


def _rango(nivel):
    return 2 if nivel == 'seguro' else 1


def marcar_repetidas(cartola, usuario):
    from ..models import Transaccion

    filas = [m for m in cartola.movimientos
             if not m.ya_existe and not m.mover_id and 'no es un gasto' not in m.aviso.lower()]
    if not filas:
        return cartola

    desde = min(m.fecha for m in filas) - timedelta(days=DIAS)
    hasta = max(m.fecha for m in filas) + timedelta(days=DIAS)
    base = list(Transaccion.objects.filter(
        usuario=usuario, fecha__range=(desde, hasta), monto__in={m.monto for m in filas},
    ).order_by('fecha', 'pk'))

    exactas = {}
    for m in cartola.movimientos:
        if m.ya_existe:
            k = (m.fecha, m.tipo, m.monto, m.descripcion.strip().lower())
            exactas[k] = exactas.get(k, 0) + 1
    usadas = set()
    for t in base:
        k = (t.fecha, t.tipo, Decimal(t.monto), (t.descripcion or '').strip().lower())
        if exactas.get(k):
            exactas[k] -= 1
            usadas.add(t.pk)

    candidatos = []
    for m in filas:
        dm, mejor = _datos_mov(m), None
        for t in base:
            if t.pk in usadas or t.tipo != m.tipo or Decimal(t.monto) != m.monto:
                continue
            nivel = clasificar(dm, _datos_tx(t))
            if not nivel:
                continue
            dias = abs((t.fecha - m.fecha).days)
            if mejor is None or (_rango(nivel), -dias) > (_rango(mejor[1]), -mejor[2]):
                mejor = (t, nivel, dias)
        if mejor:
            usadas.add(mejor[0].pk)
            candidatos.append((m, mejor[0], mejor[1]))

    dudosos = [(str(i), _datos_mov(m), _datos_tx(t))
               for i, (m, t, nivel) in enumerate(candidatos) if nivel == 'dudoso']
    respuesta = _consultar(dudosos, usuario)

    for i, (m, t, nivel) in enumerate(candidatos):
        veredicto = respuesta.get(str(i))
        if nivel == 'dudoso' and veredicto is False:
            continue
        m.reemplaza_id = t.pk
        m.reemplaza_desc = (t.descripcion or t.get_categoria_display())[:60]
        m.reemplaza_fecha = t.fecha.strftime('%d/%m')
        m.reemplaza_seguro = nivel == 'seguro' or veredicto is True
        if m.aviso:
            continue
        if nivel == 'seguro':
            m.aviso = (f'Ya la tenías anotada el {m.reemplaza_fecha}. Al guardar se reemplaza '
                       f'con la fecha y la descripción del banco.')
        elif veredicto:
            m.aviso = (f'La IA la revisó: es la que anotaste el {m.reemplaza_fecha}. Al guardar '
                       f'se reemplaza con la fecha y la descripción del banco.')
        else:
            m.aviso = (f'Podría ser la que anotaste el {m.reemplaza_fecha}. Si es la misma, '
                       f'marca «reemplazarla».')
    return cartola


def _vinculado(t):
    return bool(t.suscripcion_id) or any(hasattr(t, rel) for rel in ('pago_cuota', 'gasto_pendiente'))


def buscar_repetidos(usuario):
    from ..models import Transaccion

    grupos = {}
    for t in Transaccion.objects.filter(usuario=usuario).select_related(
            'pago_cuota', 'gasto_pendiente').order_by('fecha', 'pk'):
        grupos.setdefault((t.tipo, Decimal(t.monto)), []).append(t)

    pares = []
    for lista in grupos.values():
        if len(lista) < 2:
            continue
        for i, a in enumerate(lista):
            da = _datos_tx(a)
            for b in lista[i + 1:]:
                if (b.fecha - a.fecha).days > DIAS:
                    break
                nivel = clasificar(da, _datos_tx(b))
                if nivel:
                    pares.append((a, b, nivel, (b.fecha - a.fecha).days))
    pares.sort(key=lambda p: (-_rango(p[2]), p[3], p[0].fecha))

    usadas, elegidos = set(), []
    for a, b, nivel, _dias in pares:
        if a.pk in usadas or b.pk in usadas:
            continue
        va, vb = _vinculado(a), _vinculado(b)
        if va and vb:
            continue
        queda, borra = (b, a) if vb else (a, b)
        usadas.update((a.pk, b.pk))
        elegidos.append({'queda': queda, 'borra': borra, 'nivel': nivel})

    dudosos = [(str(i), _datos_tx(e['queda']), _datos_tx(e['borra']))
               for i, e in enumerate(elegidos) if e['nivel'] == 'dudoso']
    respuesta = _consultar(dudosos, usuario)

    salida = []
    for i, e in enumerate(elegidos):
        veredicto = respuesta.get(str(i))
        if e['nivel'] == 'dudoso' and veredicto is False:
            continue
        e['marcado'] = e['nivel'] == 'seguro' or veredicto is True
        e['por_ia'] = e['nivel'] == 'dudoso' and veredicto is True
        e['dias'] = abs((e['borra'].fecha - e['queda'].fecha).days)
        salida.append(e)
    salida.sort(key=lambda e: e['queda'].fecha, reverse=True)
    return salida
