from datetime import date

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db import transaction as db_transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..dinero import suma
from ..models import PagoServicio, SugerenciaDescartada, Suscripcion, Transaccion
from ..servicios.detectar_suscripciones import sugerencias
from ..servicios.esfera import esfera_suscripciones
from ..servicios.mes import invalidar
from ..servicios.suscripciones import generar_cobros_suscripciones
from .comun import contadores, monto_post, redirigir, simbolo_de


@login_required(login_url='/login/')
def suscripciones(request):
    subs = list(
        Suscripcion.objects.filter(usuario=request.user)
        .annotate(
            cobros_cantidad=Count('cobros'),
            cobros_total=Sum('cobros__monto'),
            cobros_pagados=Count('cobros', filter=Q(cobros__pagado=True)),
        )
        .prefetch_related('pagos')
    )
    hoy = timezone.localdate()
    for s in subs:
        es_nueva = (s.fecha_inicio.year, s.fecha_inicio.month) == (hoy.year, hoy.month)
        s.borrar_cobros_sugerido = s.cobros_pagados == 0 or (es_nueva and s.cobros_cantidad <= 1)
    activas = [s for s in subs if s.activa]
    total_mensual = sum(float(s.monto) for s in activas)

    orden = {'atrasada': 0, 'pendiente': 1, 'pagada': 2, 'pausada': 3}
    subs.sort(key=lambda s: (orden.get(s.estado_mes, 9), s.nombre))

    pendientes = [s for s in activas if not s.pagada_este_mes]
    atrasadas = [s for s in activas if s.periodos_atrasados]

    grupos = {}
    for s in activas:
        grupos.setdefault(s.categoria or 'Suscripciones', []).append(s)
    duplicadas = []
    for cat, items in grupos.items():
        if len(items) < 2:
            continue
        montos = [float(i.monto) for i in items]
        duplicadas.append({
            'categoria': cat,
            'clave': cat + ':' + ','.join(str(i.pk) for i in sorted(items, key=lambda x: x.pk)),
            'items': sorted(items, key=lambda x: float(x.monto)),
            'ahorro_anual': round((sum(montos) - min(montos)) * 12),
        })

    context = {
        'suscripciones': subs,
        'total_mensual': round(total_mensual),
        'total_anual': round(total_mensual * 12),
        'cantidad_activas': len(activas),
        'duplicadas': duplicadas,
        'ahorro_total': sum(g['ahorro_anual'] for g in duplicadas),
        'pendientes_mes': len(pendientes),
        'monto_pendiente_mes': round(suma(s.monto for s in pendientes)),
        'monto_pagado_mes': round(suma(s.monto for s in activas if s.pagada_este_mes)),
        'atrasadas': len(atrasadas),
        'monto_atrasado': round(suma(s.monto_atrasado for s in atrasadas)),
        'sugerencias': sugerencias(request.user, hoy),
    }
    context['esfera'] = esfera_suscripciones(request.user, activas, simbolo_de(request.user))
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

    with transaction.atomic():
        sub = Suscripcion.objects.select_for_update().get(pk=sub.pk)
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
        sub.cobros.filter(
            fecha__year=periodo // 100, fecha__month=periodo % 100,
        ).update(pagado=True, fecha_pago=hoy)
        invalidar(request.user.pk)

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
    sub.cobros.filter(
        fecha__year=pago.periodo // 100, fecha__month=pago.periodo % 100,
    ).update(pagado=False, fecha_pago=None)
    invalidar(request.user.pk)
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
            anterior = date(hoy.year, hoy.month, 1) - relativedelta(months=1)
            sub.ultimo_mes_generado = anterior.year * 100 + anterior.month
            sub.save(update_fields=['activa', 'fecha_cancelada', 'ultimo_mes_generado'])
            generar_cobros_suscripciones(request.user)
            messages.success(request, f'{sub.nombre} reactivada.')
    return redirect('suscripciones')

@login_required(login_url='/login/')
def editar_suscripcion(request, sub_id):
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()[:100]
        monto = monto_post(request)
        categoria = (request.POST.get('categoria', '').strip()[:50]
                     or sub.categoria or 'Suscripciones')
        try:
            dia = max(1, min(28, int(request.POST.get('dia_cobro', sub.dia_cobro))))
        except (ValueError, TypeError):
            dia = sub.dia_cobro

        if not (nombre and monto > 0):
            messages.warning(request, 'Completa nombre y monto.')
            return redirect('editar_suscripcion', sub_id=sub.pk)

        hoy = timezone.localdate()
        with db_transaction.atomic():
            sub.nombre, sub.monto, sub.categoria, sub.dia_cobro = nombre, monto, categoria, dia
            sub.save(update_fields=['nombre', 'monto', 'categoria', 'dia_cobro'])
            sub.cobros.update(descripcion=f'Suscripción: {nombre}')
            sub.cobros.filter(pagado=False, fecha__year=hoy.year, fecha__month=hoy.month).update(
                monto=monto, categoria=categoria,
                fecha=sub.fecha_cobro_de(hoy.year * 100 + hoy.month))
        invalidar(request.user.pk)
        messages.success(request, f'{nombre} actualizada.')
        return redirect('suscripciones')

    context = {'sub': sub, 'monto_entero': int(sub.monto)}
    context.update(contadores(request.user))
    return render(request, 'finanzas/editar_suscripcion.html', context)

@login_required(login_url='/login/')
def eliminar_suscripcion(request, sub_id):
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    if request.method == 'POST':
        borrar = request.POST.get('borrar_gastos') == '1'
        with db_transaction.atomic():
            cantidad = sub.cobros.count()
            if borrar and cantidad:
                sub.cobros.all().delete()
            sub.delete()
        invalidar(request.user.pk)
        if borrar and cantidad:
            messages.success(request, f'Suscripción eliminada junto con {cantidad} gasto{"s" if cantidad != 1 else ""}.')
        elif cantidad:
            messages.success(request, 'Suscripción eliminada. Sus gastos siguen en tus movimientos.')
        else:
            messages.success(request, 'Suscripción eliminada.')
    return redirect('suscripciones')

@login_required(login_url='/login/')
def agregar_sugerencia(request):
    if request.method != 'POST':
        return redirect('suscripciones')
    clave = request.POST.get('clave', '')
    hoy = timezone.localdate()
    s = next((x for x in sugerencias(request.user, hoy) if x['clave'] == clave), None)
    if not s:
        messages.warning(request, 'Esa sugerencia ya no está disponible.')
        return redirect('suscripciones')

    periodo = hoy.year * 100 + hoy.month
    with db_transaction.atomic():
        sub = Suscripcion.objects.create(
            usuario=request.user, nombre=s['nombre'], monto=s['monto'], dia_cobro=s['dia'],
            categoria=s['categoria'], fecha_inicio=hoy,
        )
        Transaccion.objects.filter(usuario=request.user, pk__in=s['ids']).update(suscripcion=sub)
        if s['cobrada_este_mes']:
            sub.ultimo_mes_generado = periodo
            sub.save(update_fields=['ultimo_mes_generado'])
            PagoServicio.objects.get_or_create(
                suscripcion=sub, periodo=periodo,
                defaults={'monto': s['monto'], 'fecha_pago': hoy},
            )
    generar_cobros_suscripciones(request.user)
    invalidar(request.user.pk)
    anual = f"{int(s['anual']):,}".replace(',', '.')
    messages.success(request, f'{sub.nombre} agregada: $' + anual + ' al año.')
    return redirect('suscripciones')

@login_required(login_url='/login/')
def descartar_sugerencia(request):
    if request.method == 'POST':
        clave = request.POST.get('clave', '')[:80]
        if clave:
            SugerenciaDescartada.objects.get_or_create(usuario=request.user, clave=clave)
            messages.success(request, 'Listo, no te la volvemos a sugerir.')
    return redirect('suscripciones')
