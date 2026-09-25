from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from ..forms import MetaAhorroForm
from ..models import AporteMeta, MetaAhorro
from ..servicios.mes import NOMBRES_MESES
from .comun import contadores, monto_post, redirigir


@login_required(login_url='/login/')
def aportar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        monto = monto_post(request)
        if monto <= 0:
            if es_ajax:
                return JsonResponse({'ok': False, 'msg': 'Ingresa un monto válido.'})
            messages.warning(request, 'Ingresa un monto válido.')
            return redirigir(request)

        AporteMeta.objects.create(meta=meta, monto=monto, nota=request.POST.get('nota', ''))
        meta.monto_actual = (meta.monto_actual or 0) + monto
        meta.save(update_fields=['monto_actual'])

        if es_ajax:
            return JsonResponse({
                'ok': True, 'nombre': meta.nombre,
                'monto_actual': float(meta.monto_actual),
                'monto_meta': float(meta.monto_meta),
                'porcentaje': round(float(meta.porcentaje), 1),
                'completada': meta.esta_completa,
            })
        messages.success(request, f'Aporte a "{meta.nombre}" registrado.')

    return redirigir(request)

@login_required(login_url='/login/')
def crear_meta(request):
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST)
        if form.is_valid():
            meta = form.save(commit=False)
            meta.usuario = request.user
            meta.save()
            messages.success(request, f"Meta '{meta.nombre}' creada.")
            return redirigir(request)
    else:
        form = MetaAhorroForm()
    context = {'form': form}
    context.update(contadores(request.user))
    return render(request, 'finanzas/crear_meta.html', context)

@login_required(login_url='/login/')
def editar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST, instance=meta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Meta actualizada.')
            return redirigir(request)
    else:
        form = MetaAhorroForm(instance=meta)
    context = {'form': form, 'editar': True, 'meta': meta}
    context.update(contadores(request.user))
    return render(request, 'finanzas/crear_meta.html', context)

@login_required(login_url='/login/')
def eliminar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        meta.delete()
        messages.success(request, 'Meta eliminada.')
    return redirigir(request)

@login_required(login_url='/login/')
def metas(request):
    hoy = date.today()
    lista = list(MetaAhorro.objects.filter(usuario=request.user)
                                   .prefetch_related('aportes'))

    meses = []
    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        meses.append({'clave': f.year * 100 + f.month,
                      'label': NOMBRES_MESES[f.month - 1]})

    datos = []
    for meta in lista:
        aportes = list(meta.aportes.all())
        por_mes = {}
        for ap in aportes:
            k = ap.fecha.year * 100 + ap.fecha.month
            por_mes[k] = por_mes.get(k, 0) + float(ap.monto)

        serie = [por_mes.get(m['clave'], 0) for m in meses]
        techo = max(serie) or 1
        ultimo = aportes[0] if aportes else None
        datos.append({
            'meta': meta,
            'serie': [{'label': meses[i]['label'],
                       'monto': round(serie[i]),
                       'alto': round(serie[i] / techo * 100)}
                      for i in range(len(meses))],
            'aportado_6m': round(sum(serie)),
            'promedio_mes': round(sum(serie) / len([s for s in serie if s]) ) if any(serie) else 0,
            'ultimo_aporte': ultimo,
            'meses_quieta': (((hoy.year - ultimo.fecha.year) * 12
                              + hoy.month - ultimo.fecha.month)
                             if ultimo else None),
        })

    datos.sort(key=lambda d: (d['meta'].esta_completa, -float(d['meta'].porcentaje)))

    context = {
        'metas_datos': datos,
        'labels_meses': [m['label'] for m in meses],
        'total_ahorrado': round(sum(float(m.monto_actual) for m in lista)),
        'total_meta': round(sum(float(m.monto_meta) for m in lista)),
        'total_faltante': round(sum(float(m.monto_faltante) for m in lista)),
        'completas': len([m for m in lista if m.esta_completa]),
        'form': MetaAhorroForm(),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/metas.html', context)
