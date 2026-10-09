import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import Categoria, TopeCategoria, Transaccion
from ..servicios.mes import nombre_mes_es
from ..servicios.mes_elegido import mes_pedido, selector_mes
from ..servicios.topes import estado_tope, gastado_por_categoria, promedio_tres_meses
from ..templatetags.moneda import money
from .comun import contadores, monto_post, simbolo_de


def _de_la_lista(valor, opciones, defecto):
    return valor if valor in dict(opciones) else defecto

@login_required(login_url='/login/')
def categorias(request):
    hoy = date.today()
    year, month = mes_pedido(request, hoy)
    _, ultimo = calendar.monthrange(year, month)
    inicio, fin = date(year, month, 1), date(year, month, ultimo)

    gastado = {
        x['categoria']: float(x['total'])
        for x in Transaccion.objects.filter(
            usuario=request.user, fecha__gte=inicio, fecha__lte=fin,
        ).values('categoria').annotate(total=Sum('monto'))
    }
    usos = {
        x['categoria']: x['n']
        for x in Transaccion.objects.filter(usuario=request.user)
                                    .values('categoria').annotate(n=Count('id'))
    }

    topes = {t.categoria: t for t in TopeCategoria.objects.filter(usuario=request.user)}
    gasto_mes = gastado_por_categoria(request.user, year, month) if topes else {}
    promedios = promedio_tres_meses(request.user, hoy)

    mapa = Categoria.mapa(request.user)
    propias_qs = list(Categoria.objects.filter(usuario=request.user))
    propias_slugs = {c.slug for c in propias_qs}

    def fila(slug, datos, obj=None):
        return {
            'slug': slug, 'label': datos['label'], 'color': datos['color'],
            'icono': datos['icono'], 'propia': datos['propia'],
            'gastado': round(gastado.get(slug, 0)),
            'usos': usos.get(slug, 0),
            'obj': obj,
            'tope': estado_tope(topes[slug], gasto_mes.get(slug, 0)) if slug in topes else None,
            'promedio': promedios.get(slug, 0),
        }

    de_gasto, de_ingreso = [], []
    slugs_ingreso = {c[0] for c in Transaccion.CATEGORIAS_INGRESO}

    for slug, datos in mapa.items():
        if slug in propias_slugs:
            continue
        destino = de_ingreso if slug in slugs_ingreso else de_gasto
        destino.append(fila(slug, datos))

    for c in propias_qs:
        destino = de_ingreso if c.tipo == "INGRESO" else de_gasto
        destino.append(fila(c.slug, mapa[c.slug], obj=c))

    de_gasto.sort(key=lambda x: -x["gastado"])
    de_ingreso.sort(key=lambda x: -x["gastado"])

    context = {
        'de_gasto': de_gasto,
        'de_ingreso': de_ingreso,
        'total_propias': len(propias_qs),
        'con_topes': len(topes),
        'sin_usar': [c for c in de_gasto + de_ingreso if c['usos'] == 0],
        'paleta': Categoria.PALETA,
        'iconos': Categoria.ICONOS,
        'nombre_mes': nombre_mes_es(year, month),
        'mes_sel': selector_mes(request.user, year, month, hoy),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/categorias.html', context)

@login_required(login_url='/login/')
def crear_categoria(request):
    if request.method != 'POST':
        return redirect('categorias')

    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        messages.warning(request, 'Ponle un nombre a la categoría.')
        return redirect('categorias')

    Categoria.objects.create(
        usuario=request.user, nombre=nombre,
        tipo=_de_la_lista(request.POST.get('tipo'), Categoria.TIPOS, 'EGRESO'),
        color=_de_la_lista(request.POST.get('color'), Categoria.PALETA, '#ffaa2c'),
        icono=_de_la_lista(request.POST.get('icono'), Categoria.ICONOS, 'fa-tag'),
    )
    messages.success(request, 'Categoría "' + nombre + '" creada.')
    return redirect('categorias')

@login_required(login_url='/login/')
@require_POST
def guardar_tope(request):
    slug = (request.POST.get('categoria') or '').strip()
    opciones = dict(Categoria.opciones(request.user, 'EGRESO'))
    if slug not in opciones:
        messages.warning(request, 'Elige una categoría de gasto.')
        return redirect('categorias')
    nombre = opciones[slug]
    if request.POST.get('quitar'):
        TopeCategoria.objects.filter(usuario=request.user, categoria=slug).delete()
        messages.success(request, f'Quitaste el tope de {nombre}.')
        return redirect('categorias')
    monto = monto_post(request)
    if monto <= 0:
        messages.warning(request, 'Escribe un monto mayor que cero.')
        return redirect('categorias')
    TopeCategoria.objects.update_or_create(
        usuario=request.user, categoria=slug,
        defaults={'monto': monto, 'avisar': request.POST.get('avisar') == '1'},
    )
    messages.success(request, f'Tope de {nombre}: {money(monto, simbolo_de(request.user))} al mes.')
    return redirect('categorias')

@login_required(login_url='/login/')
def editar_categoria(request, cat_id):
    cat = get_object_or_404(Categoria, id=cat_id, usuario=request.user)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            cat.nombre = nombre
        cat.color = _de_la_lista(request.POST.get('color'), Categoria.PALETA, cat.color)
        cat.icono = _de_la_lista(request.POST.get('icono'), Categoria.ICONOS, cat.icono)
        cat.save(update_fields=['nombre', 'color', 'icono'])
        messages.success(request, 'Categoría actualizada.')
    return redirect('categorias')

@login_required(login_url='/login/')
def eliminar_categoria(request, cat_id):
    cat = get_object_or_404(Categoria, id=cat_id, usuario=request.user)
    if request.method == 'POST':
        nombre = cat.nombre
        destino = 'Otros_Ingresos' if cat.tipo == 'INGRESO' else 'Otros'
        TopeCategoria.objects.filter(usuario=request.user, categoria=cat.slug).delete()
        movidos = Transaccion.objects.filter(
            usuario=request.user, categoria=cat.slug,
        ).update(categoria=destino)
        cat.delete()
        if movidos:
            messages.success(
                request, '"' + nombre + '" eliminada. "' + str(movidos)
                + ' movimiento(s) pasaron a Otros.')
        else:
            messages.success(request, '"' + nombre + '" eliminada.')
    return redirect('categorias')
