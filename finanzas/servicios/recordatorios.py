from datetime import timedelta

from ..models import TopeCategoria
from ..templatetags.moneda import money
from .mes import resumen_mes
from .pendientes import pendientes_del_mes
from .topes import gastado_por_categoria, porcentaje

NIVELES = (100, 80)


def _lista(nombres):
    if len(nombres) == 1:
        return nombres[0]
    return ', '.join(nombres[:-1]) + ' y ' + nombres[-1]


def _aviso_cobros(items, cuando, montos, simbolo):
    if len(items) == 1:
        i = items[0]
        verbo = 'vence' if cuando == 'Hoy' else 'se cobra'
        titulo = f'{cuando} {verbo} {i["nombre"]}'
        partes = []
        if i['tipo'] in ('cuota', 'debo'):
            partes.append(i['detalle'])
        if montos:
            partes.append(money(i['monto'], simbolo))
        cuerpo = ' · '.join(partes)
        cuerpo = (cuerpo + '. ' if cuerpo else '') + 'Toca para verlo en Fintora.'
    else:
        verbo = 'vencen' if cuando == 'Hoy' else 'se cobran'
        titulo = f'{cuando} {verbo} {len(items)} pagos'
        cuerpo = _lista([i['nombre'] for i in items[:4]])
        if len(items) > 4:
            cuerpo += f' y {len(items) - 4} más'
        cuerpo += '.'
        if montos:
            cuerpo += f' En total, {money(sum(float(i["monto"]) for i in items), simbolo)}.'
    return {'titulo': titulo, 'cuerpo': cuerpo, 'url': '/', 'etiqueta': f'cobros-{cuando.lower()}'}


def _items(usuario, hoy):
    items = pendientes_del_mes(usuario, hoy.year, hoy.month)
    manana = hoy + timedelta(days=1)
    if (manana.year, manana.month) != (hoy.year, hoy.month):
        items += pendientes_del_mes(usuario, manana.year, manana.month)
    return [i for i in items if not i['pagado']]


def avisos_topes(usuario, hoy, montos, simbolo):
    topes = list(TopeCategoria.objects.filter(usuario=usuario))
    if not topes:
        return []
    from ..models import Categoria

    periodo = hoy.year * 100 + hoy.month
    gastado = gastado_por_categoria(usuario, hoy.year, hoy.month)
    mapa = Categoria.mapa(usuario)
    avisos = []
    for t in topes:
        g = gastado.get(t.categoria, 0)
        pct = porcentaje(g, t.monto)
        nivel = next((n for n in NIVELES if pct >= n), 0)
        if not nivel:
            continue
        ya = t.aviso_nivel if t.aviso_periodo == periodo else 0
        if nivel <= ya:
            continue
        nombre = mapa.get(t.categoria, {}).get('label', t.categoria)
        if nivel == 100:
            titulo = f'Pasaste tu tope de {nombre}'
            detalle = f'Vas {money(float(g) - float(t.monto), simbolo)} por encima.'
        else:
            titulo = f'Vas en {pct} % de {nombre}'
            detalle = f'Te quedan {money(float(t.monto) - float(g), simbolo)} este mes.'
        avisos.append({'titulo': titulo,
                       'cuerpo': detalle if montos else 'Toca para ver tus categorías.',
                       'url': '/categorias/', 'etiqueta': f'tope-{t.categoria}'})
        t.aviso_periodo, t.aviso_nivel = periodo, nivel
        t.save(update_fields=['aviso_periodo', 'aviso_nivel'])
    return avisos


def _resumen_semana(usuario, hoy, items, montos, simbolo):
    fin = hoy + timedelta(days=7)
    semana = [i for i in items if hoy < i['fecha'] <= fin]
    if semana:
        vence = f'Esta semana vence{"n" if len(semana) != 1 else ""} {len(semana)} pago{"s" if len(semana) != 1 else ""}.'
    else:
        vence = 'Esta semana no vence nada.'
    if montos:
        r = resumen_mes(usuario, hoy.year, hoy.month)
        cuerpo = (f'Llevas gastado {money(r["gastos"] + r["total_cuotas_mes"], simbolo)} '
                  f'de {money(r["ingresos"], simbolo)} que entró. {vence}')
    else:
        cuerpo = vence + ' Toca para ver el detalle.'
    return {'titulo': 'Cómo va tu mes', 'cuerpo': cuerpo, 'url': '/', 'etiqueta': 'resumen'}


def avisos_del_dia(usuario, perfil, hoy, simbolo='$'):
    montos = perfil.push_montos
    avisos = []
    items = _items(usuario, hoy) if (perfil.push_vence or perfil.push_dia_antes
                                     or perfil.push_resumen) else []
    if perfil.push_vence:
        de_hoy = [i for i in items if i['fecha'] == hoy]
        if de_hoy:
            avisos.append(_aviso_cobros(de_hoy, 'Hoy', montos, simbolo))
    if perfil.push_dia_antes:
        manana = hoy + timedelta(days=1)
        de_manana = [i for i in items if i['fecha'] == manana]
        if de_manana:
            avisos.append(_aviso_cobros(de_manana, 'Mañana', montos, simbolo))
    if perfil.push_topes:
        avisos += avisos_topes(usuario, hoy, montos, simbolo)
    if perfil.push_resumen and hoy.weekday() == 6:
        avisos.append(_resumen_semana(usuario, hoy, items, montos, simbolo))
    return avisos
