from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import redirect, render

from ..models import Transaccion
from ..servicios.repetidos import buscar_repetidos, puede_usar_ia
from .comun import contadores


@login_required(login_url='/login/')
def repetidos(request):
    if request.method == 'POST':
        ids = [int(x) for x in request.POST.getlist('borrar') if x.isdigit()]
        borrables = Transaccion.objects.filter(
            usuario=request.user, pk__in=ids,
            pago_cuota__isnull=True, gasto_pendiente__isnull=True, suscripcion__isnull=True,
        )
        with db_transaction.atomic():
            n = borrables.count()
            for t in borrables:
                t.delete()
        if n:
            messages.success(request, f'Borré {n} movimiento{"s" if n != 1 else ""} repetido{"s" if n != 1 else ""}.')
        else:
            messages.info(request, 'No marcaste ningún movimiento para borrar.')
        return redirect('movimientos_repetidos')

    pares = buscar_repetidos(request.user)
    contexto = {
        'pares': pares,
        'marcados': sum(1 for p in pares if p['marcado']),
        'con_ia': puede_usar_ia(request.user),
    }
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/repetidos.html', contexto)
