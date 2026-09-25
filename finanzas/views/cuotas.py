from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from ..forms import DeudaForm
from ..models import Deuda, PagoCuota, Transaccion
from .comun import contadores, redirigir


@login_required(login_url='/login/')
def deudas(request):
    lista = list(Deuda.objects.filter(usuario=request.user).prefetch_related('pagos'))
    activas = [d for d in lista if not d.esta_saldada]

    activas.sort(key=lambda d: (
        -len(d.periodos_atrasados),
        d.dias_para_vencer if d.dias_para_vencer is not None else 9999,
    ))
    saldadas = [d for d in lista if d.esta_saldada]

    proximas = [d for d in activas if d.dias_para_vencer is not None]
    proximas.sort(key=lambda d: d.fecha_fin_estimada)

    context = {
        'deudas': activas,
        'saldadas': sorted(saldadas, key=lambda d: d.fecha_fin_estimada, reverse=True),
        'total_saldado': round(sum(float(d.monto_total) for d in saldadas)),
        'deudas_activas': len(activas),
        'total_cuotas_mes': round(sum(float(d.monto_cuota) for d in activas)),
        'total_restante': round(sum(float(d.monto_restante) for d in lista)),
        'total_pagado': round(sum(float(d.monto_pagado) for d in lista)),
        'total_atrasado': round(sum(float(d.monto_atrasado) for d in activas)),
        'cuotas_atrasadas': sum(len(d.periodos_atrasados) for d in activas),
        'total_deuda': round(sum(float(d.monto_total) for d in lista)),
        'se_libera': proximas[0] if proximas else None,
        'form': DeudaForm(),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/deudas.html', context)

@login_required(login_url='/login/')
def pagar_cuota(request, deuda_id):
    if request.method != 'POST':
        return redirigir(request)

    deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def responder(ok, msg, nivel='success'):
        if es_ajax:
            datos = {'ok': ok, 'msg': msg}
            if ok:
                datos.update({
                    'acreedor': deuda.acreedor,
                    'cuotas_pagadas': deuda.pagos.count(),
                    'cuotas_totales': deuda.cuotas_totales,
                    'porcentaje': deuda.porcentaje,
                    'terminada': deuda.esta_saldada,
                    'restante': str(deuda.monto_restante),
                    'texto_urgencia': deuda.texto_urgencia,
                })
            return JsonResponse(datos)
        getattr(messages, nivel)(request, msg)
        return redirigir(request)

    try:
        periodo = int(request.POST.get('periodo') or 0) or deuda.periodo_a_pagar
    except (ValueError, TypeError):
        periodo = deuda.periodo_a_pagar

    if periodo is None:
        return responder(False, f'{deuda.acreedor} ya está pagada por completo.', 'warning')
    if periodo not in deuda.periodos_programados:
        return responder(False, 'Ese mes no corresponde a esta compra.', 'warning')
    if deuda.esta_pagada_en(periodo):
        return responder(False, 'Esa cuota ya estaba pagada.', 'warning')

    monto = deuda.monto_cuota_de(periodo)
    fecha_cobro = deuda.fecha_cobro_de(periodo)
    hoy = timezone.localdate()
    numero = deuda.periodos_programados.index(periodo) + 1

    tx = Transaccion.objects.create(
        usuario=request.user, tipo='EGRESO', monto=monto,
        categoria=deuda.categoria,
        descripcion=f'Cuota {numero}/{deuda.cuotas_totales} — {deuda.acreedor}',
        fecha=fecha_cobro, es_cuota=True,
        pagado=True, fecha_pago=hoy,
    )
    PagoCuota.objects.create(
        deuda=deuda, periodo=periodo, monto=monto, fecha_pago=hoy, transaccion=tx,
    )

    deuda.cuotas_pagadas = deuda.pagos.count()
    deuda.save(update_fields=['cuotas_pagadas'])

    if deuda.esta_saldada:
        msg = f'{deuda.acreedor} quedó pagada por completo.'
    else:
        nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        etiqueta = f'{nombres[periodo % 100 - 1]} {periodo // 100}'
        restantes = len(deuda.periodos_pendientes)
        msg = (f'Cuota de {etiqueta} pagada. '
               f'Te queda{"n" if restantes != 1 else ""} {restantes} '
               f'cuota{"s" if restantes != 1 else ""}.')
    return responder(True, msg)

@login_required(login_url='/login/')
def anular_cuota(request, deuda_id):
    if request.method != 'POST':
        return redirigir(request)

    deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        periodo = int(request.POST.get('periodo') or 0)
    except (ValueError, TypeError):
        periodo = 0

    pago = (deuda.pagos.filter(periodo=periodo).first() if periodo
            else deuda.pagos.order_by('-periodo').first())

    if not pago:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
        messages.warning(request, 'No hay pagos que anular.')
        return redirigir(request)

    etiqueta = pago.etiqueta_mes
    if pago.transaccion:
        pago.transaccion.delete()
    pago.delete()

    deuda.cuotas_pagadas = deuda.pagos.count()
    deuda.save(update_fields=['cuotas_pagadas'])

    if es_ajax:
        return JsonResponse({
            'ok': True, 'acreedor': deuda.acreedor,
            'cuotas_pagadas': deuda.cuotas_pagadas,
            'cuotas_totales': deuda.cuotas_totales,
            'porcentaje': deuda.porcentaje,
            'restante': str(deuda.monto_restante),
            'texto_urgencia': deuda.texto_urgencia,
        })
    messages.success(request, f'Se anuló la cuota de {etiqueta} de {deuda.acreedor}.')
    return redirigir(request)

@login_required(login_url='/login/')
def crear_deuda(request):
    if request.method == 'POST':
        form = DeudaForm(request.POST)
        if form.is_valid():
            deuda = form.save(commit=False)
            deuda.usuario = request.user
            deuda.save()
            messages.success(
                request,
                f"'{deuda.acreedor}' agregada: {deuda.cuotas_totales} cuotas de "
                f"${int(deuda.monto_cuota):,}".replace(',', '.') + '.')
            return redirigir(request, 'deudas')
        messages.warning(request, 'Revisa los datos de la compra.')
    else:
        form = DeudaForm()
    context = {'form': form}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_deuda.html', context)

@login_required(login_url='/login/')
def editar_deuda(request, deuda_id):
    deuda = get_object_or_404(Deuda, id=deuda_id, usuario=request.user)
    if request.method == 'POST':
        form = DeudaForm(request.POST, instance=deuda)
        if form.is_valid():
            form.save()
            messages.success(request, 'Compra actualizada.')
            return redirigir(request, 'deudas')
    else:
        form = DeudaForm(instance=deuda)
    context = {'form': form, 'editar': True, 'deuda': deuda}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_deuda.html', context)

@login_required(login_url='/login/')
def eliminar_deuda(request, deuda_id):
    deuda = get_object_or_404(Deuda, id=deuda_id, usuario=request.user)
    if request.method == 'POST':
        nombre = deuda.acreedor
        deuda.delete()
        messages.success(request, f"'{nombre}' eliminada.")
    return redirigir(request, 'deudas')
