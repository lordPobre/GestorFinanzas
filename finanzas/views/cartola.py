import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import redirect, render

from ..cartolas import BANCOS, enriquecer, leer_cartola
from ..cartolas.base import ErrorCartola
from ..models import Deuda, Persona, Prestamo, Suscripcion, Transaccion
from .comun import contadores
from ..seguridad import limitar

log = logging.getLogger('finanzas')

SESION = 'cartola_pendiente'
DIAGNOSTICO = 'cartola_diagnostico'
MAX_MB = 6


def _a_dict(cartola):
    return {
        'banco': cartola.banco,
        'periodo': cartola.periodo,
        'cuenta': cartola.cuenta,
        'cuadra': cartola.cuadra,
        'descuadre': str(cartola.descuadre),
        'nota_cuadre': cartola.nota_cuadre,
        'saldo_inicial': str(cartola.saldo_inicial or ''),
        'saldo_final': str(cartola.saldo_final or ''),
        'movimientos': [{
            'fecha': m.fecha.isoformat(),
            'descripcion': m.descripcion,
            'monto': str(m.monto),
            'tipo': m.tipo,
            'categoria': m.categoria,
            'cuota_actual': m.cuota_actual,
            'cuota_total': m.cuota_total,
            'es_suscripcion': m.es_suscripcion,
            'ya_existe': m.ya_existe,
            'aviso': m.aviso,
        } for m in cartola.movimientos],
    }


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

        try:
            cartola = leer_cartola(archivo, request.POST.get('banco', ''),
                                   archivo.name)
            enriquecer(cartola, request.user)
        except ErrorCartola as e:
            messages.error(request, str(e))
            muestra = getattr(e, 'muestra', '')
            if muestra:
                request.session[DIAGNOSTICO] = {
                    'archivo': archivo.name[:80],
                    'motivo': str(e),
                    'texto': muestra,
                }
            return redirect('importar_cartola')
        except Exception:
            log.exception('Cartola ilegible')
            messages.error(request, 'No se pudo leer la cartola.')
            return redirect('importar_cartola')
        finally:
            archivo.close()

        request.session[SESION] = _a_dict(cartola)
        return redirect('revisar_cartola')

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
def revisar_cartola(request):
    datos = request.session.get(SESION)
    if not datos:
        messages.info(request, 'Sube una cartola para empezar.')
        return redirect('importar_cartola')

    filas = _filas(datos)
    nuevas = [f for f in filas if not f['ya_existe']]

    ctx = {
        'c': datos,
        'filas': filas,
        'total': len(filas),
        'nuevas': len(nuevas),
        'repetidas': len(filas) - len(nuevas),
        'descuadre': Decimal(datos.get('descuadre') or 0),
        'suma_ingresos': sum(f['monto_dec'] for f in nuevas if f['tipo'] == 'INGRESO'),
        'suma_egresos': sum(f['monto_dec'] for f in nuevas if f['tipo'] == 'EGRESO'),
        'cartola_cats_egreso': Transaccion.CATEGORIAS_EGRESO,
        'cartola_cats_ingreso': Transaccion.CATEGORIAS_INGRESO,
        'personas': Persona.objects.filter(usuario=request.user),
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
    creados = subs = deudas = prestamos = 0

    with db_transaction.atomic():
        for i, m in enumerate(movs):
            if not request.POST.get(f'sel_{i}'):
                continue

            desc = (request.POST.get(f'desc_{i}') or m['descripcion']).strip()[:200]
            cat = request.POST.get(f'cat_{i}') or m['categoria']
            monto = Decimal(m['monto'])
            fecha = date.fromisoformat(m['fecha'])
            es_cuota = m['cuota_total'] > 1

            Transaccion.objects.create(
                usuario=request.user,
                tipo=m['tipo'],
                monto=monto,
                categoria=cat,
                fecha=fecha,
                descripcion=desc,
                es_cuota=es_cuota,
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

            if request.POST.get(f'deuda_{i}') and es_cuota:
                restantes = m['cuota_total'] - m['cuota_actual'] + 1
                Deuda.objects.create(
                    usuario=request.user,
                    acreedor=desc[:100],
                    monto_total=monto * restantes,
                    categoria=(cat if cat in dict(Deuda.CATEGORIAS)
                               else Deuda._meta.get_field('categoria').default),
                    cuotas_totales=restantes,
                    cuotas_pagadas=1,
                    fecha_inicio=fecha,
                )
                deudas += 1

            if request.POST.get(f'deben_{i}') and m['tipo'] == 'EGRESO':
                persona = None
                pk = (request.POST.get(f'deben_persona_{i}') or '').strip()
                if pk.isdigit():
                    persona = Persona.objects.filter(pk=int(pk),
                                                     usuario=request.user).first()
                if persona is None:
                    nombre = (request.POST.get(f'deben_nombre_{i}') or '').strip()[:80]
                    if nombre:
                        persona, _ = Persona.objects.get_or_create(
                            usuario=request.user, nombre=nombre)
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

    if not creados:
        messages.info(request, 'No marcaste ningún movimiento.')
        return redirect('importar_cartola')

    partes = [f'{creados} movimiento{"s" if creados != 1 else ""}']
    if subs:
        partes.append(f'{subs} suscripción{"es" if subs != 1 else ""}')
    if deudas:
        partes.append(f'{deudas} compra{"s" if deudas != 1 else ""} en cuotas')
    if prestamos:
        partes.append(f'{prestamos} en Me deben')
    messages.success(request, 'Importado: ' + ', '.join(partes) + '.')
    return redirect('dashboard')


@login_required
def descartar_cartola(request):
    request.session.pop(SESION, None)
    return redirect('importar_cartola')
