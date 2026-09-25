from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..forms import TransaccionForm
from ..models import GastoPendiente, Transaccion
from .comun import contadores, monto_post, redirigir


@login_required(login_url='/login/')
def registrar_transaccion(request):
    tipo_inicial = request.GET.get('tipo', 'INGRESO')
    if request.method == 'POST':
        form = TransaccionForm(request.POST, usuario=request.user)
        if form.is_valid():
            t = form.save(commit=False)
            t.usuario = request.user
            marcado_pendiente = (request.POST.get('sin_pagar')
                                 or request.POST.get('es_pendiente'))
            if t.tipo == 'EGRESO' and marcado_pendiente:
                t.pagado = False
                t.fecha_pago = None
            else:
                t.pagado = True
                t.fecha_pago = t.fecha
            t.save()
            if t.tipo == 'EGRESO' and not t.pagado:
                messages.success(request, 'Gasto anotado como pendiente de pago.')
            else:
                messages.success(request, f'{"Ingreso" if t.es_ingreso else "Gasto"} registrado.')
            return redirigir(request)

        for campo, errores in form.errors.items():
            etiqueta = form.fields[campo].label or campo
            messages.warning(request, f'{etiqueta}: {errores[0]}')
        if request.POST.get('next'):
            return redirigir(request)
        tipo_inicial = request.POST.get('tipo', tipo_inicial)
    else:
        form = TransaccionForm(initial={'tipo': tipo_inicial, 'fecha': timezone.localdate()})

    context = {'form': form, 'tipo_inicial': tipo_inicial}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_transaccion.html', context)

@login_required(login_url='/login/')
def editar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=t, usuario=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimiento actualizado.')
            return redirigir(request)
    else:
        form = TransaccionForm(instance=t, usuario=request.user)
    context = {'form': form, 'editar': True, 'tipo_inicial': t.tipo}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_transaccion.html', context)

@login_required(login_url='/login/')
def eliminar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        t.delete()
        messages.success(request, 'Movimiento eliminado.')
    return redirigir(request)

@login_required(login_url='/login/')
def pagar_gasto(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return redirigir(request)

    if not t.es_gasto_unico:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'Solo aplica a gastos.'})
        messages.warning(request, 'Eso no es un gasto que se marque a mano.')
        return redirigir(request)

    if not t.pagado:
        t.pagado = True
        t.fecha_pago = timezone.localdate()
        t.save(update_fields=['pagado', 'fecha_pago'])

    if es_ajax:
        return JsonResponse({'ok': True, 'pagado': True,
                             'texto': t.texto_estado_pago})
    messages.success(request, f'{t.descripcion or t.get_categoria_display()}: marcado como pagado.')
    return redirigir(request)

@login_required(login_url='/login/')
def anular_pago_gasto(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return redirigir(request)

    if t.pagado and t.es_gasto_unico:
        t.pagado = False
        t.fecha_pago = None
        t.save(update_fields=['pagado', 'fecha_pago'])

    if es_ajax:
        return JsonResponse({'ok': True, 'pagado': False})
    messages.success(request, 'Marcado como no pagado.')
    return redirigir(request)

@login_required(login_url='/login/')
def registrar_ingreso(request):
    return redirect('/registrar/?tipo=INGRESO')

@login_required(login_url='/login/')
def crear_gasto_pendiente(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        monto = monto_post(request)
        fecha_venc = request.POST.get('fecha_vencimiento')
        categoria = request.POST.get('categoria', 'Cuentas').strip() or 'Cuentas'

        if not (nombre and monto > 0 and fecha_venc):
            messages.warning(request, 'Completa nombre, monto y fecha.')
            return redirigir(request)

        try:
            venc = datetime.strptime(fecha_venc, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.warning(request, 'La fecha no es válida.')
            return redirigir(request)

        tx = Transaccion.objects.create(
            usuario=request.user, tipo='EGRESO', monto=monto,
            categoria=categoria, descripcion=f'Pendiente: {nombre}',
            fecha=venc, es_cuota=False, pagado=False,
        )
        GastoPendiente.objects.create(
            usuario=request.user, nombre=nombre, monto=monto,
            fecha_vencimiento=venc, categoria=categoria, transaccion=tx,
        )
        messages.success(request, 'Gasto pendiente agregado y contabilizado.')
        return redirigir(request)

    context = {}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_gasto_pendiente.html', context)

@login_required(login_url='/login/')
def pagar_gasto_pendiente(request, gasto_id):
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and not gasto.pagado:
        gasto.pagado = True
        gasto.fecha_pago = date.today()
        gasto.save(update_fields=['pagado', 'fecha_pago'])
        if gasto.transaccion:
            gasto.transaccion.pagado = True
            gasto.transaccion.fecha_pago = gasto.fecha_pago
            gasto.transaccion.save(update_fields=['pagado', 'fecha_pago'])
        if es_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, f'{gasto.nombre} marcado como pagado.')
    return redirigir(request)

@login_required(login_url='/login/')
def anular_gasto_pendiente(request, gasto_id):
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and gasto.pagado:
        gasto.pagado = False
        gasto.fecha_pago = None
        gasto.save(update_fields=['pagado', 'fecha_pago'])
        if gasto.transaccion:
            gasto.transaccion.pagado = False
            gasto.transaccion.fecha_pago = None
            gasto.transaccion.save(update_fields=['pagado', 'fecha_pago'])
        if es_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, 'Marcado como no pagado.')
    return redirigir(request)

@login_required(login_url='/login/')
def eliminar_gasto_pendiente(request, gasto_id):
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    if request.method == 'POST':
        if gasto.transaccion:
            gasto.transaccion.delete()
        gasto.delete()
        messages.success(request, 'Gasto pendiente eliminado.')
    return redirigir(request)
