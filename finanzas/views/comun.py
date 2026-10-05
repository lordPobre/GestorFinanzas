from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import F
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

from ..forms import TransaccionForm
from ..models import Categoria, Deuda, Persona, Suscripcion, UserProfile
from ..redirecciones import destino_seguro
from ..servicios.mes import salud_financiera


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(usuario=user)
    return profile

def redirigir(request, por_defecto='dashboard'):
    destino = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if not destino:
        return redirect(por_defecto)

    if destino.startswith('?'):
        base = destino_seguro(request, request.POST.get('next_path'), request.path)
        if base == request.path:
            base = reverse(por_defecto)
        return redirect(f'{base}{destino}')

    seguro = destino_seguro(request, destino)
    if seguro:
        return redirect(seguro)

    if '/' not in destino and ':' not in destino:
        try:
            return redirect(destino)
        except NoReverseMatch:
            pass

    return redirect(por_defecto)

MONTO_MAXIMO = Decimal('99999999.99')

def monto_post(request, campo='monto'):
    try:
        valor = Decimal(str(request.POST.get(campo, '0')).strip().replace('.', '').replace(',', '.'))
    except (InvalidOperation, ValueError, AttributeError):
        return Decimal('0')
    if not valor.is_finite() or valor <= 0 or valor > MONTO_MAXIMO:
        return Decimal('0')
    return valor.quantize(Decimal('0.01'))

def texto_post(request, campo, modelo, nombre_campo=None, defecto=''):
    largo = modelo._meta.get_field(nombre_campo or campo).max_length
    texto = ' '.join(str(request.POST.get(campo, defecto) or '').split())
    return texto[:largo] if largo else texto

def contadores(usuario, resumen_actual=None):
    cuotas_activas = Deuda.objects.filter(
        usuario=usuario, cuotas_pagadas__lt=F('cuotas_totales')).count()
    personas = Persona.objects.filter(usuario=usuario).prefetch_related('prestamos__abonos')
    prestamos_activos = sum(len(p.prestamos_activos) for p in personas)
    total_por_cobrar = round(sum(p.total_pendiente for p in personas))
    hoy = date.today()
    datos = {
        'cuotas_activas': cuotas_activas,
        'prestamos_activos': prestamos_activos,
        'total_por_cobrar': total_por_cobrar,

        'profile': get_or_create_profile(usuario),

        'form_registro': TransaccionForm(initial={'tipo': 'EGRESO', 'fecha': hoy}),
        'hoy_iso': hoy.isoformat(),
        'cats_egreso': Categoria.opciones(usuario, 'EGRESO'),
        'cats_ingreso': Categoria.opciones(usuario, 'INGRESO'),
        'cats_egreso_json': [list(c) for c in Categoria.opciones(usuario, 'EGRESO')],
        'cats_ingreso_json': [list(c) for c in Categoria.opciones(usuario, 'INGRESO')],

        'subs_pendientes': sum(
            1 for s in Suscripcion.objects.filter(usuario=usuario, activa=True)
                                          .prefetch_related('pagos')
            if not s.pagada_este_mes
        ),
    }
    datos.update(salud_financiera(usuario, resumen_actual=resumen_actual))
    return datos

def simbolo_de(user):
    from ..context_processors import CONFIG_MONEDA
    try:
        return CONFIG_MONEDA.get(user.profile.moneda, CONFIG_MONEDA['CLP'])['simbolo']
    except (AttributeError, KeyError, UserProfile.DoesNotExist):
        return '$'
