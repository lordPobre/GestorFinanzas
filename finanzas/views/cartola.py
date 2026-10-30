import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from ..cartolas import BANCOS
from ..categorias_base import SLUGS_BASE
from ..models import (Categoria, Deuda, GastoPendiente, PagoCuota, Persona, Prestamo, Suscripcion,
                      Transaccion)
from ..servicios import lectura_cartola
from .comun import contadores
from ..seguridad import limitar

log = logging.getLogger('finanzas')

SESION = 'cartola_pendiente'
DIAGNOSTICO = 'cartola_diagnostico'
MAX_MB = 6


def _filas(datos):
    filas = []
    for i, m in enumerate(datos['movimientos']):
        a, t = m['cuota_actual'], m['cuota_total']
        filas.append({
            **m,
            'i': i,
            'fecha_obj': date.fromisoformat(m['fecha']),
            'monto_dec': Decimal(m['monto']),
            'es_cuota': t > 1,
            'texto_cuota': f'Cuota {a} de {t}' if t > 1 else '',
            'cuotas_deben': (t - a + 1) if t > 1 else 1,
            'monto_deben': Decimal(m['monto']) * ((t - a + 1) if t > 1 else 1),
            'marcada': not m['ya_existe'],
        })
    return filas


def _entregar(request, datos):
    if datos.get('ok'):
        request.session[SESION] = datos['cartola']
        return reverse('revisar_cartola')
    motivo = datos.get('msg') or 'No se pudo leer la cartola.'
    messages.error(request, motivo)
    if datos.get('muestra'):
        request.session[DIAGNOSTICO] = {'archivo': datos.get('archivo', ''), 'motivo': motivo,
                                        'texto': datos['muestra']}
    return reverse('importar_cartola')


def _deuda_previa(request, m, i):
    if not (m.get('deuda_id') and m.get('deuda_periodo') and request.POST.get(f'cuota_{i}')):
        return None
    return Deuda.objects.select_for_update().filter(pk=m['deuda_id'], usuario=request.user).first()


def _unir_a_la_cuota(deuda, periodo, monto, fecha, tx):
    if periodo not in deuda.periodos_programados or PagoCuota.objects.filter(transaccion=tx).exists():
        return 0
    pago = deuda.pagos.filter(periodo=periodo).first()
    if pago is None:
        PagoCuota.objects.create(deuda=deuda, periodo=periodo, monto=monto, fecha_pago=fecha,
                                 transaccion=tx)
        return 1
    if pago.transaccion_id is None:
        pago.transaccion = tx
        pago.fecha_pago = fecha
        pago.save(update_fields=['transaccion', 'fecha_pago'])
        return 1
    return 0


def _prestamo_previo(request, m, i):
    return bool(m.get('prestamo_id') and request.POST.get(f'prestamo_{i}')
                and Prestamo.objects.filter(pk=m['prestamo_id'], persona__usuario=request.user,
                                            persona__lado='ME_DEBE').exists())


@login_required
@limitar(20, 3600, 'Demasiadas cartolas seguidas. Prueba en un rato.')
def importar_cartola(request):
    if request.method == 'POST':
        archivo = request.FILES.get('cartola')
        if not archivo:
            messages.error(request, 'Elige el archivo de la cartola.')
            return redirect('importar_cartola')

        if archivo.size > MAX_MB * 1024 * 1024:
            messages.error(request, f'El archivo pasa de {MAX_MB} MB.')
            return redirect('importar_cartola')

        request.session.pop(DIAGNOSTICO, None)
        request.session.pop(SESION, None)
        banco = request.POST.get('banco', '')
        nombre = archivo.name
        try:
            contenido = archivo.read()
        finally:
            archivo.close()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            firmado = lectura_cartola.lanzar(request.user, contenido, banco, nombre)
            del contenido
            if firmado is None:
                return JsonResponse({'ok': False, 'msg': 'Ahora hay varias cartolas leyéndose. Prueba en un minuto.'},
                                    status=503)
            return JsonResponse({'ok': True, 'tarea': firmado})

        datos = lectura_cartola.leer_ahora(request.user, contenido, banco, nombre)
        del contenido
        return redirect(_entregar(request, datos))

    cuentas, tarjetas = [], []
    for clave, lector in BANCOS.items():
        destino = tarjetas if getattr(lector, 'es_tarjeta', False) else cuentas
        destino.append((clave, lector.nombre))

    ctx = {'grupos': [('Cartola de cuenta corriente, vista o ahorro', cuentas),
                      ('Estado de cuenta de tarjeta', tarjetas)],
           'diagnostico': request.session.pop(DIAGNOSTICO, None)}
    ctx.update(contadores(request.user))
    return render(request, 'finanzas/importar_cartola.html', ctx)


@login_required
@require_GET
def tarea_cartola(request):
    datos = lectura_cartola.estado(request.user, request.GET.get('t', ''))
    if datos is None:
        return JsonResponse({'listo': True, 'url': reverse('importar_cartola')}, status=404)
    if not datos.get('listo'):
        return JsonResponse({'listo': False})
    return JsonResponse({'listo': True, 'url': _entregar(request, datos)})


@login_required
def revisar_cartola(request):
    datos = request.session.get(SESION)
    if not datos:
        messages.info(request, 'Sube una cartola para empezar.')
        return redirect('importar_cartola')

    filas = _filas(datos)
    nuevas = [f for f in filas if not f['ya_existe']]
    cats = Categoria.opciones_por_tipo(request.user)

    ctx = {
        'c': datos,
        'filas': filas,
        'total': len(filas),
        'nuevas': len(nuevas),
        'repetidas': len(filas) - len(nuevas),
        'reemplazos': sum(1 for f in nuevas if f.get('reemplaza_id')),
        'conocidas': sum(1 for f in nuevas if f.get('deuda_id') or f.get('prestamo_id')),
        'descuadre': Decimal(datos.get('descuadre') or 0),
        'suma_ingresos': sum(f['monto_dec'] for f in nuevas if f['tipo'] == 'INGRESO'),
        'suma_egresos': sum(f['monto_dec'] for f in nuevas if f['tipo'] == 'EGRESO'),
        'cartola_cats_egreso': cats['EGRESO'],
        'cartola_cats_ingreso': cats['INGRESO'],
        'personas': Persona.objects.filter(usuario=request.user, lado='ME_DEBE'),
    }
    ctx.update(contadores(request.user))
    return render(request, 'finanzas/revisar_cartola.html', ctx)


@login_required
def confirmar_cartola(request):
    if request.method != 'POST':
        return redirect('revisar_cartola')

    datos = request.session.get(SESION)
    if not datos:
        messages.info(request, 'La revisión expiró. Sube la cartola otra vez.')
        return redirect('importar_cartola')

    movs = datos['movimientos']
    creados = movidos = reemplazados = subs = deudas = prestamos = pagadas = ajenas = 0
    cats = Categoria.opciones_por_tipo(request.user)
    validas = {tipo: {slug for slug, _ in cats[tipo]} | SLUGS_BASE
              for tipo in ('INGRESO', 'EGRESO')}

    with db_transaction.atomic():
        for i, m in enumerate(movs):
            if not request.POST.get(f'sel_{i}'):
                continue

            desc = (request.POST.get(f'desc_{i}') or m['descripcion']).strip()[:200]
            cat = request.POST.get(f'cat_{i}') or m['categoria']
            if cat not in validas.get(m['tipo'], set()):
                cat = (m['categoria'] if m['categoria'] in validas.get(m['tipo'], set())
                       else 'Otros_Ingresos' if m['tipo'] == 'INGRESO' else 'Otros')
            monto = Decimal(m['monto'])
            fecha = date.fromisoformat(m['fecha'])
            es_cuota = m['cuota_total'] > 1

            anterior = None
            if m.get('mover_id'):
                anterior = Transaccion.objects.filter(
                    pk=m['mover_id'], usuario=request.user).first()
            if anterior is not None:
                anterior.fecha = fecha
                anterior.fecha_pago = fecha
                anterior.save()
                movidos += 1
                continue

            previa = None
            if m.get('reemplaza_id') and request.POST.get(f'reemplazar_{i}'):
                previa = Transaccion.objects.filter(
                    pk=m['reemplaza_id'], usuario=request.user, tipo=m['tipo']).first()
            deuda_previa = _deuda_previa(request, m, i)
            if deuda_previa is not None and previa is None:
                pago = (deuda_previa.pagos.filter(periodo=m['deuda_periodo'], transaccion__isnull=False)
                        .select_related('transaccion').first())
                if pago is not None:
                    previa = pago.transaccion
            if previa is not None and deuda_previa is None and previa.por_pagar and previa.fecha > fecha:
                previa.descripcion = desc
                previa.save(update_fields=['descripcion'])
                reemplazados += 1
                continue
            if previa is not None:
                previa.fecha = fecha
                previa.descripcion = desc
                previa.pagado = True
                previa.fecha_pago = fecha
                if deuda_previa is not None:
                    previa.es_cuota = True
                GastoPendiente.objects.filter(transaccion=previa, pagado=False).update(
                    pagado=True, fecha_pago=fecha)
                previa.save()
                reemplazados += 1
                if deuda_previa is not None:
                    pagadas += _unir_a_la_cuota(deuda_previa, m['deuda_periodo'], monto, fecha, previa)
                continue

            tx = Transaccion.objects.create(
                usuario=request.user,
                tipo=m['tipo'],
                monto=monto,
                categoria=cat,
                fecha=fecha,
                descripcion=desc,
                es_cuota=es_cuota,
                origen=Transaccion.CARTOLA,
                pagado=True,
                fecha_pago=fecha,
            )
            creados += 1

            if request.POST.get(f'sub_{i}'):
                Suscripcion.objects.get_or_create(
                    usuario=request.user, nombre=desc[:100],
                    defaults={
                        'monto': monto,
                        'categoria': cat,
                        'dia_cobro': min(fecha.day, 28),
                        'fecha_inicio': fecha,
                    },
                )
                subs += 1

            if deuda_previa is not None:
                pagadas += _unir_a_la_cuota(deuda_previa, m['deuda_periodo'], monto, fecha, tx)
            elif request.POST.get(f'deuda_{i}') and es_cuota:
                restantes = m['cuota_total'] - m['cuota_actual'] + 1
                deuda = Deuda.objects.create(
                    usuario=request.user,
                    acreedor=desc[:100],
                    monto_total=monto * restantes,
                    categoria=(cat if m['tipo'] == 'EGRESO'
                               else Deuda.CATEGORIA_DEFECTO),
                    cuotas_totales=restantes,
                    cuotas_pagadas=0,
                    fecha_inicio=fecha,
                )
                PagoCuota.objects.create(
                    deuda=deuda, periodo=fecha.year * 100 + fecha.month,
                    monto=monto, fecha_pago=fecha, transaccion=tx,
                )
                deudas += 1

            if _prestamo_previo(request, m, i):
                ajenas += 1
            elif deuda_previa is None and request.POST.get(f'deben_{i}') and m['tipo'] == 'EGRESO':
                persona = None
                pk = (request.POST.get(f'deben_persona_{i}') or '').strip()
                if pk.isdigit():
                    persona = Persona.objects.filter(pk=int(pk), usuario=request.user,
                                                     lado='ME_DEBE').first()
                if persona is None:
                    nombre = (request.POST.get(f'deben_nombre_{i}') or '').strip()[:80]
                    if nombre:
                        persona, _ = Persona.objects.get_or_create(
                            usuario=request.user, nombre=nombre, lado='ME_DEBE')
                if persona is not None:
                    restantes = (m['cuota_total'] - m['cuota_actual'] + 1
                                 if es_cuota else 1)
                    Prestamo.objects.create(
                        persona=persona,
                        descripcion=desc[:120],
                        monto=monto * restantes,
                        tipo='CUOTAS' if restantes > 1 else 'UNICO',
                        cuotas_totales=restantes,
                        fecha=fecha,
                    )
                    prestamos += 1

    request.session.pop(SESION, None)

    if not creados and not movidos and not reemplazados:
        messages.info(request, 'No marcaste ningún movimiento.')
        return redirect('importar_cartola')

    partes = []
    if creados:
        partes.append(f'{creados} movimiento{"s" if creados != 1 else ""}')
    if movidos:
        partes.append(f'{movidos} movido{"s" if movidos != 1 else ""} al mes de su ciclo')
    if reemplazados:
        partes.append(f'{reemplazados} reemplazo{"s" if reemplazados != 1 else ""} de uno que ya tenías')
    if subs:
        partes.append(f'{subs} suscripción{"es" if subs != 1 else ""}')
    if deudas:
        partes.append(f'{deudas} compra{"s" if deudas != 1 else ""} en cuotas')
    if prestamos:
        partes.append(f'{prestamos} en Me deben')
    if pagadas:
        partes.append(f'{pagadas} cuota{"s" if pagadas != 1 else ""} '
                      f'pagada{"s" if pagadas != 1 else ""} en Cuotas')
    if ajenas:
        partes.append(f'{ajenas} cuota{"s" if ajenas != 1 else ""} de compras que ya estaban en Préstamos')
    messages.success(request, 'Importado: ' + ', '.join(partes) + '.')
    return redirect('dashboard')


@login_required
def descartar_cartola(request):
    request.session.pop(SESION, None)
    return redirect('importar_cartola')
