from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import AbonoPrestamo, Persona, Prestamo
from .comun import contadores, monto_post, redirigir


def _totales_prestamos(personas):
    return {
        'total_por_cobrar': round(sum(p.total_pendiente for p in personas)),
        'total_prestado': round(sum(p.total_prestado for p in personas)),
        'total_recuperado': round(sum(p.total_abonado for p in personas)),
    }

@login_required(login_url='/login/')
def prestamos(request):
    personas = list(Persona.objects.filter(usuario=request.user)
                    .prefetch_related('prestamos__abonos'))

    seleccionada = None
    pedida = request.GET.get('persona')
    if pedida:
        seleccionada = next((p for p in personas if str(p.id) == str(pedida)), None)
    if seleccionada is None and personas:
        seleccionada = max(personas, key=lambda p: p.total_pendiente)

    context = {
        'personas': personas,
        'persona': seleccionada,
        'prestamos': list(seleccionada.prestamos.all()) if seleccionada else [],
    }
    context.update(_totales_prestamos(personas))
    context.update(contadores(request.user))
    return render(request, 'finanzas/prestamos.html', context)

@login_required(login_url='/login/')
def detalle_persona(request, persona_id):
    personas = list(Persona.objects.filter(usuario=request.user)
                    .prefetch_related('prestamos__abonos'))

    persona = next((p for p in personas if p.id == persona_id), None)
    if persona is None:
        raise Http404('Persona no encontrada')

    context = {
        'persona': persona,
        'personas': personas,
        'prestamos': list(persona.prestamos.all()),
    }
    context.update(_totales_prestamos(personas))
    context.update(contadores(request.user))
    return render(request, 'finanzas/prestamos.html', context)

@login_required(login_url='/login/')
def crear_persona(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        contacto = request.POST.get('contacto', '').strip()
        if not nombre:
            messages.warning(request, 'Ingresa un nombre.')
            return redirigir(request, 'prestamos')

        persona = Persona.objects.create(usuario=request.user, nombre=nombre, contacto=contacto)
        messages.success(request, f'{nombre} agregado.')

        monto = monto_post(request)
        if monto > 0:
            tipo = request.POST.get('tipo', 'UNICO')
            try:
                cuotas = int(request.POST.get('cuotas_totales', 1)) if tipo == 'CUOTAS' else 1
            except (ValueError, TypeError):
                cuotas = 1
            Prestamo.objects.create(
                persona=persona,
                descripcion=request.POST.get('descripcion', '').strip() or 'Préstamo',
                monto=monto, tipo=tipo, cuotas_totales=max(1, cuotas),
            )
        return redirect('detalle_persona', persona_id=persona.id)

    context = {}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_persona.html', context)

@login_required(login_url='/login/')
def crear_prestamo(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id, usuario=request.user)
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion', '').strip()
        monto = monto_post(request)
        if not descripcion or monto <= 0:
            messages.warning(request, 'Revisa la descripción y el monto.')
            return redirect('detalle_persona', persona_id=persona.id)

        tipo = request.POST.get('tipo', 'UNICO')
        try:
            cuotas = int(request.POST.get('cuotas_totales', 1)) if tipo == 'CUOTAS' else 1
        except (ValueError, TypeError):
            cuotas = 1
        cuotas = max(1, cuotas)

        p = Prestamo.objects.create(
            persona=persona, descripcion=descripcion,
            monto=monto, tipo=tipo, cuotas_totales=cuotas,
        )
        if tipo == 'CUOTAS':
            messages.success(
                request,
                f'Préstamo registrado: {cuotas} cuotas de '
                f'${int(p.monto_cuota):,}'.replace(',', '.') + '.')
        else:
            messages.success(request, 'Préstamo registrado.')
        return redirect('detalle_persona', persona_id=persona.id)

    context = {'persona': persona}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_prestamo.html', context)

@login_required(login_url='/login/')
def abonar_prestamo(request, prestamo_id):
    prestamo = get_object_or_404(Prestamo, id=prestamo_id, persona__usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        monto = monto_post(request)
        if monto <= 0:
            if es_ajax:
                return JsonResponse({'ok': False, 'msg': 'Ingresa un monto válido.'})
            messages.warning(request, 'Ingresa un monto válido.')
            return redirect('detalle_persona', persona_id=prestamo.persona.id)

        pendiente = Decimal(str(prestamo.monto_pendiente))
        if monto > pendiente:
            monto = pendiente

        AbonoPrestamo.objects.create(
            prestamo=prestamo, monto=monto,
            nota=request.POST.get('nota', ''), fecha=timezone.localdate(),
        )

        if es_ajax:
            return JsonResponse({
                'ok': True,
                'pendiente': prestamo.monto_pendiente,
                'porcentaje': prestamo.porcentaje,
                'pagado': prestamo.esta_pagado,
                'cuotas_abonadas': prestamo.cuotas_abonadas,
            })
        if prestamo.esta_pagado:
            messages.success(request, f'{prestamo.persona.nombre} quedó al día.')
        else:
            messages.success(request, 'Abono registrado.')
    return redirect('detalle_persona', persona_id=prestamo.persona.id)

@login_required(login_url='/login/')
def eliminar_persona(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id, usuario=request.user)
    if request.method == 'POST':
        nombre = persona.nombre
        persona.delete()
        messages.success(request, f'{nombre} y sus préstamos fueron eliminados.')
    return redirect('prestamos')

@login_required(login_url='/login/')
def eliminar_prestamo(request, prestamo_id):
    prestamo = get_object_or_404(Prestamo, id=prestamo_id, persona__usuario=request.user)
    persona_id = prestamo.persona.id
    if request.method == 'POST':
        prestamo.delete()
        messages.success(request, 'Préstamo eliminado.')
    return redirect('detalle_persona', persona_id=persona_id)
