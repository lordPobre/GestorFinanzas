from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .. import fechas
from ..models import IngresoFijo, IngresoMes
from ..models.ingresos import nombre_periodo, periodo_de
from ..servicios import ingreso_fijo
from ..servicios.mes_elegido import mes_pedido
from .comun import contadores, monto_post, texto_post


def _plata(valor):
    return '$' + f'{int(valor):,}'.replace(',', '.')


def _volver(periodo=None):
    destino = reverse('ingresos')
    if periodo:
        destino += f'?mes={periodo // 100}-{periodo % 100:02d}'
    return redirect(destino)


def _dia(request):
    texto = (request.POST.get('dia_otro') or '').strip() or (request.POST.get('dia_pago') or '').strip()
    try:
        dia = int(texto)
    except ValueError:
        return 30
    return dia if 0 <= dia <= 31 else 30


def _mes_valido(request):
    try:
        periodo = int(request.POST.get('periodo') or 0)
    except ValueError:
        periodo = 0
    ingreso = ingreso_fijo.de(request.user)
    hoy = fechas.hoy()
    if ingreso is None or not 1 <= periodo % 100 <= 12:
        return None, periodo, hoy
    if not ingreso.inicio <= periodo <= periodo_de(hoy):
        return None, periodo, hoy
    return ingreso, periodo, hoy


@login_required(login_url='/login/')
def ingresos(request):
    hoy = fechas.hoy()
    year, month = mes_pedido(request, hoy)
    contexto = ingreso_fijo.pantalla(request.user, year * 100 + month, hoy)
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/ingresos_2c.html', contexto)


@login_required(login_url='/login/')
@require_POST
def guardar_ingreso(request):
    monto = monto_post(request)
    if monto <= 0:
        messages.warning(request, 'Escribe cuánto te llega al mes.')
        return _volver()
    nombre = texto_post(request, 'nombre', IngresoFijo)
    if ingreso_fijo.guardar(request.user, nombre, monto, _dia(request), fechas.hoy()):
        messages.success(request, 'Sueldo guardado. Cada mes queda por recibir hasta que llegue.')
    else:
        messages.success(request, 'Sueldo actualizado.')
    return _volver()


@login_required(login_url='/login/')
@require_POST
def ajustar_ingreso(request):
    ingreso, periodo, _ = _mes_valido(request)
    if ingreso is None:
        messages.warning(request, 'Ese mes no se puede cambiar.')
        return _volver()
    nombre = nombre_periodo(periodo)
    if request.POST.get('modo') == 'monto':
        nuevo = monto_post(request, 'nuevo')
        if nuevo <= 0:
            messages.warning(request, f'Escribe lo que recibes en {nombre}.')
            return _volver(periodo)
        adelante = request.POST.get('alcance') == 'adelante'
        ingreso_fijo.cambiar_monto(ingreso, periodo, nuevo, adelante)
        if adelante:
            messages.success(request, f'Desde {nombre}, tu sueldo es {_plata(nuevo)}.')
        else:
            messages.success(request, f'En {nombre} recibes {_plata(nuevo)}. Los otros meses siguen igual.')
        return _volver(periodo)
    extra = monto_post(request, 'extra')
    ingreso_fijo.ajustar_extra(ingreso, periodo, extra, texto_post(request, 'nota', IngresoMes))
    if extra > 0:
        messages.success(request, f'Horas extra de {nombre}: {_plata(extra)}.')
    else:
        messages.success(request, f'{nombre.capitalize()} queda sin horas extra.')
    return _volver(periodo)


@login_required(login_url='/login/')
@require_POST
def ingreso_llego(request):
    ingreso, periodo, hoy = _mes_valido(request)
    if ingreso is None:
        messages.warning(request, 'Ese mes todavía no llega.')
        return _volver()
    fila = ingreso_fijo.llego(ingreso, periodo, hoy)
    if fila is None:
        messages.info(request, f'Tu sueldo de {nombre_periodo(periodo)} ya estaba recibido.')
    elif fila.anotado_aqui:
        messages.success(request, f'Sueldo de {nombre_periodo(periodo)} recibido: '
                                  f'{_plata(fila.monto_recibido)} en tus ingresos.')
    else:
        messages.success(request, f'Sueldo de {nombre_periodo(periodo)} recibido con el ingreso que ya tenías.')
    return _volver(periodo)


@login_required(login_url='/login/')
@require_POST
def ingreso_deshacer(request):
    ingreso, periodo, _ = _mes_valido(request)
    if ingreso is None:
        return _volver()
    if ingreso_fijo.deshacer(ingreso, periodo):
        messages.success(request, f'Tu sueldo de {nombre_periodo(periodo)} vuelve a quedar por recibir.')
    return _volver(periodo)


@login_required(login_url='/login/')
@require_POST
def quitar_ingreso(request):
    if ingreso_fijo.quitar(request.user):
        messages.success(request, 'Quitaste tu ingreso fijo. Lo que ya llegó sigue en tus movimientos.')
    return _volver()
