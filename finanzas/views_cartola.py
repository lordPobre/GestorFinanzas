"""Importar movimientos desde el PDF de una cartola.

Tres pasos, y el del medio es el que importa:

    subir  ->  REVISAR  ->  confirmar

Nunca se inserta nada directo. Un parser que se equivoca en silencio y mete
cuarenta gastos falsos deja la app peor que no tener la función: hay que
borrarlos uno por uno y mientras tanto ningún número es confiable. Así que
la cartola propone y la persona confirma.

El PDF no se guarda. Se lee del request en memoria, se extrae el texto y el
archivo se descarta ahí mismo: una cartola trae el número de cuenta y el
saldo, y no hay ninguna razón para que eso quede en el disco del servidor.
Lo que viaja al paso siguiente es la lista ya interpretada, en la sesión.
"""
import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import redirect, render

from .cartolas import BANCOS, enriquecer, leer_cartola
from .cartolas.base import ErrorCartola
from .models import Deuda, Suscripcion, Transaccion
# El contexto que base.html da por sentado: el perfil del saludo, las
# categorías del panel "Anotar gasto" y los contadores del menú. Cada vista
# tiene que aplicarlo; sin él la pantalla sale con el avatar en "?" y el
# panel de registro vacío.
from .views import contadores
from .seguridad import limitar

log = logging.getLogger('finanzas')

SESION = 'cartola_pendiente'
MAX_MB = 6


# ---------------------------------------------------------------------
#  La sesión guarda dicts, no objetos: tiene que poder serializarse a JSON.
# ---------------------------------------------------------------------

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
    """Los dicts de la sesión, listos para el template."""
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
            # Se preselecciona todo menos lo que ya está en la base: es la
            # decisión correcta en la enorme mayoría de las filas, y las
            # excepciones se destildan de a una.
            'marcada': not m['ya_existe'],
        })
    return filas


# ---------------------------------------------------------------------
#  Paso 1 y 2
# ---------------------------------------------------------------------

@login_required
@limitar(20, 3600, 'Demasiadas cartolas seguidas. Prueba en un rato.')
def importar_cartola(request):
    if request.method == 'POST':
        archivo = request.FILES.get('cartola')
        if not archivo:
            messages.error(request, 'Elige el PDF de la cartola.')
            return redirect('importar_cartola')

        if archivo.size > MAX_MB * 1024 * 1024:
            messages.error(request, f'El archivo pasa de {MAX_MB} MB.')
            return redirect('importar_cartola')

        try:
            cartola = leer_cartola(archivo, request.POST.get('banco', ''))
            enriquecer(cartola, request.user)
        except ErrorCartola as e:
            messages.error(request, str(e))
            return redirect('importar_cartola')
        except Exception:
            log.exception('Cartola ilegible')
            messages.error(request, 'No se pudo leer la cartola.')
            return redirect('importar_cartola')
        finally:
            # El PDF muere acá, pase lo que pase. Si Django lo escribió a un
            # temporal por tamaño, close() lo borra.
            archivo.close()

        request.session[SESION] = _a_dict(cartola)
        return redirect('revisar_cartola')

    ctx = {'bancos': [(c, p.nombre) for c, p in BANCOS.items()]}
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
        # La sesión guarda strings; el filtro |money necesita un número.
        'descuadre': Decimal(datos.get('descuadre') or 0),
        'suma_ingresos': sum(f['monto_dec'] for f in nuevas if f['tipo'] == 'INGRESO'),
        'suma_egresos': sum(f['monto_dec'] for f in nuevas if f['tipo'] == 'EGRESO'),
        # Con prefijo a propósito: base.html ya tiene sus propios cats_egreso
        # y cats_ingreso (pares valor/etiqueta) que alimentan los chips del
        # modal de registro. Pisarlos desde acá rompía esa plantilla en toda
        # la pantalla, no solo en este bloque.
        'cartola_cats_egreso': Transaccion.CATEGORIAS_EGRESO,
        'cartola_cats_ingreso': Transaccion.CATEGORIAS_INGRESO,
    }
    ctx.update(contadores(request.user))
    return render(request, 'finanzas/revisar_cartola.html', ctx)


# ---------------------------------------------------------------------
#  Paso 3
# ---------------------------------------------------------------------

@login_required
def confirmar_cartola(request):
    if request.method != 'POST':
        return redirect('revisar_cartola')

    datos = request.session.get(SESION)
    if not datos:
        messages.info(request, 'La revisión expiró. Sube la cartola otra vez.')
        return redirect('importar_cartola')

    movs = datos['movimientos']
    creados = subs = deudas = 0

    # Todo o nada: si una fila revienta a mitad de camino, no quedan veinte
    # movimientos importados y treinta afuera sin saber cuáles.
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
                # Viene de la cartola: la plata ya se movió de verdad.
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
                        # El día del cobro sale de la fecha del movimiento;
                        # se topa en 28 para que exista en febrero.
                        'dia_cobro': min(fecha.day, 28),
                        'fecha_inicio': fecha,
                    },
                )
                subs += 1

            if request.POST.get(f'deuda_{i}') and es_cuota:
                total = m['cuota_total']
                Deuda.objects.create(
                    usuario=request.user,
                    acreedor=desc[:100],
                    monto_total=monto * total,
                    # Deuda tiene su propia lista de categorías, más corta que
                    # la de Transaccion. Si la elegida no está ahí se deja el
                    # default del modelo en vez de guardar un valor huérfano
                    # que después ninguna pantalla sabe pintar.
                    categoria=(cat if cat in dict(Deuda.CATEGORIAS)
                               else Deuda._meta.get_field('categoria').default),
                    cuotas_totales=total,
                    cuotas_pagadas=m['cuota_actual'],
                    fecha_inicio=fecha,
                )
                deudas += 1

    request.session.pop(SESION, None)

    if not creados:
        messages.info(request, 'No marcaste ningún movimiento.')
        return redirect('importar_cartola')

    partes = [f'{creados} movimiento{"s" if creados != 1 else ""}']
    if subs:
        partes.append(f'{subs} suscripción{"es" if subs != 1 else ""}')
    if deudas:
        partes.append(f'{deudas} compra{"s" if deudas != 1 else ""} en cuotas')
    messages.success(request, 'Importado: ' + ', '.join(partes) + '.')
    return redirect('dashboard')


@login_required
def descartar_cartola(request):
    request.session.pop(SESION, None)
    return redirect('importar_cartola')
