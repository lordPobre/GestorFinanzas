from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import PagoServicio, Suscripcion, Transaccion
from ..servicios.suscripciones import generar_cobros_suscripciones
from .comun import contadores, monto_post, redirigir


@login_required(login_url='/login/')
def suscripciones(request):
    subs = list(Suscripcion.objects.filter(usuario=request.user).prefetch_related('pagos'))
    activas = [s for s in subs if s.activa]
    total_mensual = sum(float(s.monto) for s in activas)

    orden = {'atrasada': 0, 'pendiente': 1, 'pagada': 2, 'pausada': 3}
    subs.sort(key=lambda s: (orden.get(s.estado_mes, 9), s.nombre))

    pendientes = [s for s in activas if not s.pagada_este_mes]
    atrasadas = [s for s in activas if s.periodos_atrasados]

    grupos = {}
    for s in activas:
        grupos.setdefault(s.categoria or 'Suscripciones', []).append(s)
    duplicadas = [{'categoria': cat, 'items': items,
                   'ahorro_anual': round(min(float(i.monto) for i in items) * 12)}
                  for cat, items in grupos.items() if len(items) > 1]

    context = {
        'suscripciones': subs,
        'total_mensual': round(total_mensual),
        'total_anual': round(total_mensual * 12),
        'cantidad_activas': len(activas),
        'duplicadas': duplicadas,
        'pendientes_mes': len(pendientes),
        'monto_pendiente_mes': round(sum(float(s.monto) for s in pendientes)),
        'monto_pagado_mes': round(sum(float(s.monto) for s in activas if s.pagada_este_mes)),
        'atrasadas': len(atrasadas),
        'monto_atrasado': round(sum(float(s.monto_atrasado) for s in atrasadas)),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/suscripciones.html', context)

@login_required(login_url='/login/')
def crear_suscripcion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        monto = monto_post(request)
        categoria = request.POST.get('categoria', 'Suscripciones').strip() or 'Suscripciones'
        try:
            dia = max(1, min(28, int(request.POST.get('dia_cobro', '1'))))
        except (ValueError, TypeError):
            dia = 1

        if not (nombre and monto > 0):
            messages.warning(request, 'Completa nombre y monto.')
            return redirect('suscripciones')

        Suscripcion.objects.create(
            usuario=request.user, nombre=nombre, monto=monto,
            dia_cobro=dia, categoria=categoria, fecha_inicio=date.today(),
        )
        generar_cobros_suscripciones(request.user)
        messages.success(
            request,
            f'{nombre} agregada: ${int(monto * 12):,}'.replace(',', '.') + ' al año.')
        return redirect('suscripciones')

    context = {}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_suscripcion.html', context)

@login_required(login_url='/login/')
def pagar_servicio(request, sub_id):
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def responder(ok, msg, nivel='success'):
        if es_ajax:
            datos = {'ok': ok, 'msg': msg}
            if ok:
                datos.update({
                    'nombre': sub.nombre,
                    'estado': sub.estado_mes,
                    'texto_estado': sub.texto_estado,
                    'texto_a_pagar': sub.texto_a_pagar,
                    'pagada_este_mes': sub.pagada_este_mes,
                })
            return JsonResponse(datos)
        getattr(messages, nivel)(request, msg)
        return redirigir(request, 'suscripciones')

    if request.method != 'POST':
        return redirigir(request, 'suscripciones')

    try:
        periodo = int(request.POST.get('periodo') or 0) or sub.periodo_a_pagar
    except (ValueError, TypeError):
        periodo = sub.periodo_a_pagar

    if periodo is None:
        return responder(False, f'{sub.nombre} ya está al día.', 'warning')
    if periodo not in sub.periodos_programados:
        return responder(False, 'Ese mes todavía no se ha cobrado.', 'warning')
    if sub.esta_pagada_en(periodo):
        return responder(False, 'Ese mes ya estaba pagado.', 'warning')

    hoy = timezone.localdate()
    PagoServicio.objects.create(
        suscripcion=sub, periodo=periodo, monto=sub.monto, fecha_pago=hoy,
    )
    Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO', es_cuota=False,
        descripcion=f'Suscripción: {sub.nombre}',
        fecha__year=periodo // 100, fecha__month=periodo % 100,
    ).update(pagado=True, fecha_pago=hoy)

    restantes = len(sub.periodos_pendientes)
    if restantes:
        msg = (f'{sub.nombre}: mes pagado. '
               f'Te queda{"n" if restantes != 1 else ""} {restantes} sin pagar.')
    else:
        msg = f'{sub.nombre} quedó al día.'
    return responder(True, msg)

@login_required(login_url='/login/')
def anular_pago_servicio(request, sub_id):
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return redirigir(request, 'suscripciones')

    try:
        periodo = int(request.POST.get('periodo') or 0)
    except (ValueError, TypeError):
        periodo = 0

    pago = (sub.pagos.filter(periodo=periodo).first() if periodo
            else sub.pagos.order_by('-periodo').first())

    if not pago:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
        messages.warning(request, 'No hay pagos que anular.')
        return redirigir(request, 'suscripciones')

    etiqueta = pago.etiqueta_mes
    Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO', es_cuota=False,
        descripcion=f'Suscripción: {sub.nombre}',
        fecha__year=pago.periodo // 100, fecha__month=pago.periodo % 100,
    ).update(pagado=False, fecha_pago=None)
    pago.delete()

    if es_ajax:
        return JsonResponse({'ok': True, 'estado': sub.estado_mes,
                             'texto_estado': sub.texto_estado})
    messages.success(request, f'{sub.nombre}: se anuló el pago de {etiqueta}.')
    return redirigir(request, 'suscripciones')

@login_required(login_url='/login/')
def cancelar_suscripcion(request, sub_id):
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    if request.method == 'POST':
        if sub.activa:
            sub.activa = False
            sub.fecha_cancelada = date.today()
            sub.save(update_fields=['activa', 'fecha_cancelada'])
            messages.success(
                request,
                f'{sub.nombre} cancelada. Ahorras ${int(sub.monto_anual):,}'.replace(',', '.')
                + ' al año.')
        else:
            sub.activa = True
            sub.fecha_cancelada = None
            hoy = date.today()
            sub.ultimo_mes_generado = hoy.year * 100 + hoy.month - 1
            sub.save(update_fields=['activa', 'fecha_cancelada', 'ultimo_mes_generado'])
            generar_cobros_suscripciones(request.user)
            messages.success(request, f'{sub.nombre} reactivada.')
    return redirect('suscripciones')

@login_required(login_url='/login/')
def eliminar_suscripcion(request, sub_id):
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    if request.method == 'POST':
        sub.delete()
        messages.success(request, 'Suscripción eliminada.')
    return redirect('suscripciones')
