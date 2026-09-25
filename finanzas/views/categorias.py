import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Categoria, Transaccion
from ..servicios.mes import nombre_mes_es
from .comun import contadores


@login_required(login_url='/login/')
def categorias(request):
    hoy = date.today()
    _, ultimo = calendar.monthrange(hoy.year, hoy.month)
    inicio, fin = date(hoy.year, hoy.month, 1), date(hoy.year, hoy.month, ultimo)

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
        'sin_usar': [c for c in de_gasto + de_ingreso if c['usos'] == 0],
        'paleta': Categoria.PALETA,
        'iconos': Categoria.ICONOS,
        'nombre_mes': nombre_mes_es(hoy.year, hoy.month),
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
        tipo=request.POST.get('tipo', 'EGRESO'),
        color=request.POST.get('color', '#ffaa2c'),
        icono=request.POST.get('icono', 'fa-tag'),
    )
    messages.success(request, 'Categoría "' + nombre + '" creada.')
    return redirect('categorias')

@login_required(login_url='/login/')
def editar_categoria(request, cat_id):
    cat = get_object_or_404(Categoria, id=cat_id, usuario=request.user)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            cat.nombre = nombre
        cat.color = request.POST.get('color', cat.color)
        cat.icono = request.POST.get('icono', cat.icono)
        cat.save(update_fields=['nombre', 'color', 'icono'])
        messages.success(request, 'Categoría actualizada.')
    return redirect('categorias')

@login_required(login_url='/login/')
def eliminar_categoria(request, cat_id):
    cat = get_object_or_404(Categoria, id=cat_id, usuario=request.user)
    if request.method == 'POST':
        nombre = cat.nombre
        destino = 'Otros_Ingresos' if cat.tipo == 'INGRESO' else 'Otros'
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
