import calendar
import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from dateutil.relativedelta import relativedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.db.models import F, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import DeudaForm, MetaAhorroForm, TransaccionForm
from .models import (AbonoPrestamo, AporteMeta, Deuda, GastoPendiente,
                     MetaAhorro, Persona, Prestamo, Presupuesto, Suscripcion,
                     Transaccion, UserProfile)

NOMBRES_MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


# ============================================================
#  HELPERS
# ============================================================

def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(usuario=user)
    return profile


def _redirigir(request, por_defecto='dashboard'):
    """Vuelve a la pantalla desde la que se hizo la acción.

    Antes todo redirigía a 'dashboard', así que pagar una cuota desde la
    pantalla de cuotas te sacaba de ahí. Ahora respeta ?next=.
    """
    destino = request.POST.get('next') or request.GET.get('next')
    if destino:
        return redirect(destino)
    return redirect(por_defecto)


def _monto_post(request, campo='monto'):
    """Lee un monto del POST sin reventar si viene basura."""
    try:
        return Decimal(str(request.POST.get(campo, '0')).replace('.', '').replace(',', '.'))
    except (InvalidOperation, ValueError, AttributeError):
        return Decimal('0')


def resumen_mes(usuario, year, month):
    """Los números del mes en un solo lugar.

    Antes esta lógica vivía dentro de dashboard(), así que el panel de
    registro, la vista de cuotas y el análisis no podían reusarla y cada
    pantalla mostraba un 'disponible' distinto. Ahora es una función.
    """
    _, ultimo_dia = calendar.monthrange(year, month)
    fecha_inicio = date(year, month, 1)
    fecha_fin = date(year, month, ultimo_dia)
    hoy = date.today()

    ingresos = float(Transaccion.objects.filter(
        usuario=usuario, tipo='INGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin,
    ).aggregate(t=Sum('monto'))['t'] or 0)

    # Gastos del día a día. Excluye los pagos de cuotas (es_cuota=True)
    # porque las cuotas del mes se suman aparte, completas.
    gastos = float(Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin, es_cuota=False,
    ).aggregate(t=Sum('monto'))['t'] or 0)

    deudas = Deuda.objects.filter(usuario=usuario)
    cuotas_pagadas = 0.0
    cuotas_pendientes = 0.0
    eventos = {}

    for d in deudas:
        dia_venc = min(d.fecha_inicio.day, ultimo_dia)
        fecha_cobro = date(year, month, dia_venc)
        fecha_fin_deuda = d.fecha_inicio + relativedelta(months=int(d.cuotas_totales) - 1)
        if not (d.fecha_inicio <= fecha_cobro <= fecha_fin_deuda):
            continue

        if (year, month) < (hoy.year, hoy.month):
            estado = 'pagado'
        elif (year, month) > (hoy.year, hoy.month):
            estado = 'pendiente'
        elif d.esta_saldada or (d.proximo_vencimiento and d.proximo_vencimiento > fecha_cobro):
            estado = 'pagado'
        else:
            estado = 'pendiente'

        monto = float(d.monto_cuota)
        if estado == 'pagado':
            cuotas_pagadas += monto
        else:
            cuotas_pendientes += monto

        eventos.setdefault(dia_venc, []).append({
            'deuda': d, 'estado': estado, 'monto': d.monto_cuota,
        })

    total_cuotas = cuotas_pagadas + cuotas_pendientes
    comprometido = gastos + total_cuotas
    disponible = ingresos - comprometido

    # Días que quedan del mes. Si se está mirando un mes pasado o futuro,
    # se usa el mes completo para que "por día" siga teniendo sentido.
    if (year, month) == (hoy.year, hoy.month):
        dias_restantes = max(1, ultimo_dia - hoy.day + 1)
    else:
        dias_restantes = ultimo_dia

    base = max(ingresos, 1.0)
    return {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'ultimo_dia': ultimo_dia,
        'ingresos': ingresos,
        'gastos': gastos,
        'cuotas_pagadas_mes': cuotas_pagadas,
        'cuotas_pendientes_mes': cuotas_pendientes,
        'total_cuotas_mes': total_cuotas,
        'comprometido': comprometido,
        'disponible': disponible,
        'dias_restantes': dias_restantes,
        'por_dia': max(0.0, disponible) / dias_restantes,
        # Porcentajes de la barra apilada del encabezado
        'pct_gastado': round(min(100, gastos / base * 100)),
        'pct_por_pagar': round(min(100, cuotas_pendientes / base * 100)),
        'pct_disponible': round(min(100, max(0.0, disponible) / base * 100)),
        'eventos': eventos,
    }


def contadores(usuario):
    """Los números del menú lateral. Se pasan en todas las vistas para que
    los badges no aparezcan solo en el dashboard."""
    cuotas_activas = Deuda.objects.filter(
        usuario=usuario, cuotas_pagadas__lt=F('cuotas_totales')).count()
    personas = Persona.objects.filter(usuario=usuario).prefetch_related('prestamos__abonos')
    prestamos_activos = sum(len(p.prestamos_activos) for p in personas)
    return {
        'cuotas_activas': cuotas_activas,
        'prestamos_activos': prestamos_activos,
    }


def generar_cobros_suscripciones(usuario):
    """Genera los cobros mensuales de suscripciones activas que falten.
    Se llama al abrir el dashboard (generación perezosa).
    Cada cobro se registra como gasto del mes (transacción EGRESO)."""
    hoy = date.today()
    mes_actual_clave = hoy.year * 100 + hoy.month

    for sub in Suscripcion.objects.filter(usuario=usuario, activa=True):
        if sub.ultimo_mes_generado == 0:
            cursor = date(sub.fecha_inicio.year, sub.fecha_inicio.month, 1)
        else:
            ultimo_anio = sub.ultimo_mes_generado // 100
            ultimo_mes = sub.ultimo_mes_generado % 100
            cursor = date(ultimo_anio, ultimo_mes, 1) + relativedelta(months=1)

        genero_algo = False
        while cursor.year * 100 + cursor.month <= mes_actual_clave:
            _, ult_dia = calendar.monthrange(cursor.year, cursor.month)
            dia = min(sub.dia_cobro, ult_dia)
            Transaccion.objects.create(
                usuario=usuario, tipo='EGRESO', monto=sub.monto,
                categoria=sub.categoria or 'Suscripciones',
                descripcion=f'Suscripción: {sub.nombre}',
                fecha=date(cursor.year, cursor.month, dia), es_cuota=False,
            )
            sub.ultimo_mes_generado = cursor.year * 100 + cursor.month
            cursor = cursor + relativedelta(months=1)
            genero_algo = True

        # Antes se guardaba siempre, incluso sin cambios: un UPDATE por
        # suscripción en cada carga del dashboard.
        if genero_algo:
            sub.save(update_fields=['ultimo_mes_generado'])


# ============================================================
#  DASHBOARD
# ============================================================

@login_required(login_url='/login/')
def dashboard(request):
    generar_cobros_suscripciones(request.user)
    hoy = date.today()

    try:
        year = int(request.GET.get('year', hoy.year))
        month = int(request.GET.get('month', hoy.month))
        date(year, month, 1)
    except ValueError:
        year, month = hoy.year, hoy.month

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    r = resumen_mes(request.user, year, month)
    nombre_mes = date(year, month, 1).strftime('%B %Y').capitalize()
    todas_las_deudas = Deuda.objects.filter(usuario=request.user)

    # ---------- Calendario ----------
    calendario_datos = []
    for semana in calendar.monthcalendar(year, month):
        fila = []
        for dia in semana:
            if dia == 0:
                fila.append(None)
            else:
                eventos = r['eventos'].get(dia, [])
                fila.append({
                    'numero': dia,
                    'es_hoy': (dia == hoy.day and month == hoy.month and year == hoy.year),
                    'eventos': eventos,
                    # Nuevos: el template ya no tiene que recorrer los eventos
                    'tiene_pagos': bool(eventos),
                    'todo_pagado': bool(eventos) and all(e['estado'] == 'pagado' for e in eventos),
                    'total_dia': sum(float(e['monto']) for e in eventos),
                })
        calendario_datos.append(fila)

    dias_con_pago = [d for semana in calendario_datos for d in semana if d and d['tiene_pagos']]

    # ---------- Serie de 6 meses ----------
    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = [], [], [], []
    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        rr = resumen_mes(request.user, f.year, f.month)
        meses_labels.append(f"{NOMBRES_MESES[f.month - 1]} {f.year}")
        datos_ingresos.append(rr['ingresos'])
        datos_gastos.append(rr['gastos'])
        datos_cuotas.append(rr['total_cuotas_mes'])

    # ---------- Categorías ----------
    gastos_categoria = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=r['fecha_inicio'], fecha__lte=r['fecha_fin'],
    ).values('categoria').annotate(total=Sum('monto')).order_by('-total')

    total_cat = sum(float(x['total']) for x in gastos_categoria) or 1.0
    categorias = []
    etiquetas = dict(Transaccion.CATEGORIAS)
    for x in gastos_categoria:
        cat = x['categoria'] or 'Otros'
        categorias.append({
            'nombre': cat,
            'label': etiquetas.get(cat, cat),
            'total': float(x['total']),
            'porcentaje': round(float(x['total']) / total_cat * 100),
            'color': Transaccion.COLORES_CATEGORIA.get(cat, Transaccion.COLORES_CATEGORIA['Otros']),
        })

    # ---------- Próximo pago ----------
    pendientes = [d for d in todas_las_deudas
                  if not d.esta_saldada and d.dias_para_vencer is not None]
    pendientes.sort(key=lambda d: d.dias_para_vencer)
    proximo_pago = pendientes[0] if pendientes else None

    ultimas = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]
    deuda_total = sum(float(d.monto_restante) for d in todas_las_deudas if not d.esta_saldada)
    metas = MetaAhorro.objects.filter(usuario=request.user)
    es_nuevo = (r['ingresos'] == 0 and r['gastos'] == 0 and not todas_las_deudas.exists())

    # ---------- Insights ----------
    insights = []

    presupuesto = Presupuesto.objects.filter(usuario=request.user).first()
    presupuesto_pct = None
    if presupuesto and presupuesto.limite_mensual > 0:
        limite = float(presupuesto.limite_mensual)
        presupuesto_pct = round((r['gastos'] / limite) * 100)
        if presupuesto_pct >= 100:
            insights.append({
                'tipo': 'peligro', 'icono': 'fa-exclamation-triangle',
                'texto': f'Superaste tu presupuesto mensual ({presupuesto_pct}%). Llevas gastado más de lo planeado.',
            })
        elif presupuesto_pct >= 80:
            insights.append({
                'tipo': 'alerta', 'icono': 'fa-exclamation-triangle',
                'texto': f'Vas en el {presupuesto_pct}% de tu presupuesto. Cuida los gastos del resto del mes.',
            })

    if len(datos_gastos) >= 2 and datos_gastos[-2] > 0:
        variacion = round(((datos_gastos[-1] - datos_gastos[-2]) / datos_gastos[-2]) * 100)
        if variacion >= 20:
            insights.append({'tipo': 'alerta', 'icono': 'fa-arrow-up',
                             'texto': f'Gastaste {variacion}% más que el mes pasado.'})
        elif variacion <= -20:
            insights.append({'tipo': 'exito', 'icono': 'fa-arrow-down',
                             'texto': f'Gastaste {abs(variacion)}% menos que el mes pasado. ¡Bien!'})

    urgentes = [d for d in pendientes if d.urgencia in ('vencida', 'critica')]
    for d in urgentes[:2]:
        dias = d.dias_para_vencer
        if dias < 0:
            insights.append({
                'tipo': 'peligro', 'icono': 'fa-credit-card',
                'texto': f'La cuota de {d.acreedor} está vencida hace {abs(dias)} día{"s" if abs(dias) != 1 else ""}.',
            })
        else:
            insights.append({
                'tipo': 'alerta', 'icono': 'fa-credit-card',
                'texto': f'La cuota de {d.acreedor} vence en {dias} día{"s" if dias != 1 else ""}.',
            })

    proyecciones_deuda = []
    for d in todas_las_deudas:
        if d.esta_saldada:
            continue
        fin = d.fecha_fin_estimada
        proyecciones_deuda.append({
            'acreedor': d.acreedor,
            'fecha_fin': fin,
            'cuotas_restantes': d.cuotas_restantes,
            'monto_cuota': float(d.monto_cuota),
            'mes_fin': f'{NOMBRES_MESES[fin.month - 1]} {fin.year}',
        })
    proyecciones_deuda.sort(key=lambda x: x['fecha_fin'])
    if proyecciones_deuda:
        prox = proyecciones_deuda[0]
        insights.append({
            'tipo': 'info', 'icono': 'fa-check-circle',
            'texto': f'A este ritmo, terminas de pagar {prox["acreedor"]} en {prox["mes_fin"]}.',
        })

    # Lo que se libera cuando termine la deuda más próxima
    se_libera = proyecciones_deuda[0] if proyecciones_deuda else None

    context = {
        'nombre_mes': nombre_mes,
        'profile': get_or_create_profile(request.user),
        'es_nuevo': es_nuevo,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],

        # Números del mes
        'total_ingresos': round(r['ingresos']),
        'total_gastos': round(r['gastos']),
        'total_cuotas_mes': round(r['total_cuotas_mes']),
        'cuotas_pagadas_mes': round(r['cuotas_pagadas_mes']),
        'cuotas_pendientes_mes': round(r['cuotas_pendientes_mes']),
        'ya_gaste': round(r['gastos']),
        'total_comprometido_mes': round(r['comprometido']),
        'disponible': round(r['disponible']),
        'deuda_total': round(deuda_total),

        # Nuevos: los usa el encabezado "Puedes gastar X hasta fin de mes"
        'por_pagar': round(r['cuotas_pendientes_mes']),
        'dias_restantes': r['dias_restantes'],
        'por_dia': round(r['por_dia']),
        'pct_gastado': r['pct_gastado'],
        'pct_por_pagar': r['pct_por_pagar'],
        'pct_disponible': r['pct_disponible'],
        'proximo_pago': proximo_pago,
        'se_libera': se_libera,
        'categorias': categorias,
        'dias_con_pago': dias_con_pago,
        'subs_pendientes': Suscripcion.objects.filter(usuario=request.user, activa=True).count(),

        'insights': insights,
        'presupuesto': presupuesto,
        'presupuesto_pct': presupuesto_pct,
        'proyecciones_deuda': proyecciones_deuda,
        'deudas': [e['deuda'] for dia in r['eventos'].values() for e in dia],
        'gastos_pendientes': GastoPendiente.objects.filter(usuario=request.user, pagado=False),
        'ultimas': ultimas,
        'metas': metas,
        'calendario': calendario_datos,

        # Formulario del panel de registro, para no salir del dashboard
        'form': TransaccionForm(initial={'tipo': 'EGRESO'}),

        'meses_json': json.dumps(meses_labels),
        'ingresos_json': json.dumps(datos_ingresos),
        'gastos_json': json.dumps(datos_gastos),
        'cuotas_json': json.dumps(datos_cuotas),
        'cat_labels_json': json.dumps([c['label'] for c in categorias]),
        'cat_data_json': json.dumps([c['total'] for c in categorias]),
        'cat_colores_json': json.dumps([c['color'] for c in categorias]),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/dashboard.html', context)


# ============================================================
#  COMPRAS EN CUOTAS
# ============================================================

@login_required(login_url='/login/')
def deudas(request):
    """Pantalla propia para las compras en cuotas.

    Antes las deudas solo se veían dentro del dashboard, mezcladas con todo
    lo demás, y no había dónde ver el avance de cada una.
    """
    lista = list(Deuda.objects.filter(usuario=request.user))
    activas = [d for d in lista if not d.esta_saldada]

    # Orden: primero lo que vence antes; las saldadas al final.
    activas.sort(key=lambda d: d.dias_para_vencer if d.dias_para_vencer is not None else 9999)
    saldadas = [d for d in lista if d.esta_saldada]

    proximas = [d for d in activas if d.dias_para_vencer is not None]
    proximas.sort(key=lambda d: d.fecha_fin_estimada)

    context = {
        'deudas': activas + saldadas,
        'deudas_activas': len(activas),
        'total_cuotas_mes': round(sum(float(d.monto_cuota) for d in activas)),
        'total_restante': round(sum(float(d.monto_restante) for d in lista)),
        'total_pagado': round(sum(float(d.monto_pagado) for d in lista)),
        'total_deuda': round(sum(float(d.monto_total) for d in lista)),
        'se_libera': proximas[0] if proximas else None,
        'form': DeudaForm(),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/deudas.html', context)


@login_required(login_url='/login/')
def pagar_cuota(request, deuda_id):
    if request.method != 'POST':
        return _redirigir(request)

    deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if deuda.esta_saldada:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'Ya está pagada.'})
        messages.warning(request, f'{deuda.acreedor} ya está pagada.')
        return _redirigir(request)

    deuda.cuotas_pagadas += 1
    deuda.save(update_fields=['cuotas_pagadas'])

    Transaccion.objects.create(
        usuario=request.user, tipo='EGRESO',
        monto=deuda.monto_cuota, categoria=deuda.categoria,
        descripcion=f'Cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} — {deuda.acreedor}',
        # Antes: timezone.now() (un datetime en un DateField).
        fecha=timezone.localdate(),
        es_cuota=True,
    )

    if es_ajax:
        return JsonResponse({
            'ok': True, 'acreedor': deuda.acreedor,
            'cuotas_pagadas': deuda.cuotas_pagadas,
            'cuotas_totales': deuda.cuotas_totales,
            'porcentaje': deuda.porcentaje,
            'terminada': deuda.esta_saldada,
            'monto': str(deuda.monto_cuota),
            'restante': str(deuda.monto_restante),
        })
    messages.success(
        request,
        f'Cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} de {deuda.acreedor} pagada.')
    return _redirigir(request)


@login_required(login_url='/login/')
def anular_cuota(request, deuda_id):
    if request.method != 'POST':
        return _redirigir(request)

    deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if deuda.cuotas_pagadas <= 0:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
        messages.warning(request, 'No hay pagos que anular.')
        return _redirigir(request)

    # Se busca la transacción por su descripción exacta antes de decrementar.
    # Antes se usaba descripcion__icontains=acreedor, que podía borrar la
    # cuota de otra deuda con nombre parecido ("Visa" y "Visa Oro").
    etiqueta = f'Cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} — {deuda.acreedor}'
    tx = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO', es_cuota=True, descripcion=etiqueta,
    ).order_by('-fecha', '-id').first()
    if tx:
        tx.delete()

    deuda.cuotas_pagadas -= 1
    deuda.save(update_fields=['cuotas_pagadas'])

    if es_ajax:
        return JsonResponse({
            'ok': True, 'acreedor': deuda.acreedor,
            'cuotas_pagadas': deuda.cuotas_pagadas,
            'cuotas_totales': deuda.cuotas_totales,
            'porcentaje': deuda.porcentaje,
            'restante': str(deuda.monto_restante),
        })
    messages.success(request, f'Se anuló una cuota de {deuda.acreedor}.')
    return _redirigir(request)


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
            return _redirigir(request, 'deudas')
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
            return _redirigir(request, 'deudas')
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
    return _redirigir(request, 'deudas')


# ============================================================
#  TRANSACCIONES
# ============================================================

@login_required(login_url='/login/')
def registrar_transaccion(request):
    tipo_inicial = request.GET.get('tipo', 'INGRESO')
    if request.method == 'POST':
        form = TransaccionForm(request.POST)
        if form.is_valid():
            t = form.save(commit=False)
            t.usuario = request.user
            t.save()
            messages.success(request, f'{"Ingreso" if t.es_ingreso else "Gasto"} registrado.')
            return _redirigir(request)
        messages.warning(request, 'Revisa el monto y la categoría.')
        tipo_inicial = request.POST.get('tipo', tipo_inicial)
    else:
        form = TransaccionForm(initial={'tipo': tipo_inicial})

    context = {'form': form, 'tipo_inicial': tipo_inicial}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_transaccion.html', context)


@login_required(login_url='/login/')
def editar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=t)
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimiento actualizado.')
            return _redirigir(request)
    else:
        form = TransaccionForm(instance=t)
    context = {'form': form, 'editar': True, 'tipo_inicial': t.tipo}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_transaccion.html', context)


@login_required(login_url='/login/')
def eliminar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        t.delete()
        messages.success(request, 'Movimiento eliminado.')
    return _redirigir(request)


@login_required(login_url='/login/')
def registrar_ingreso(request):
    return redirect('/registrar/?tipo=INGRESO')


# ============================================================
#  ESTADÍSTICAS
# ============================================================

@login_required(login_url='/login/')
def estadisticas(request):
    hoy = date.today()
    activas = [d for d in Deuda.objects.filter(usuario=request.user) if not d.esta_saldada]

    labels = [d.acreedor for d in activas]
    data_cuota = [float(d.monto_cuota) for d in activas]
    data_restante = [float(d.monto_restante) for d in activas]

    # Serie de 12 meses para el gráfico de rango, y el ranking de categorías.
    meses, ingresos, gastos = [], [], []
    for i in range(11, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        r = resumen_mes(request.user, f.year, f.month)
        meses.append(f'{NOMBRES_MESES[f.month - 1]} {f.year}')
        ingresos.append(r['ingresos'])
        gastos.append(r['gastos'] + r['total_cuotas_mes'])

    gastos_reales = [g for g in gastos if g > 0]
    promedio = sum(gastos_reales) / len(gastos_reales) if gastos_reales else 0
    ahorros = [ingresos[i] - gastos[i] for i in range(len(meses))]
    mejor = ahorros.index(max(ahorros)) if ahorros else None
    peor = gastos.index(max(gastos)) if gastos else None
    total_ing = sum(ingresos) or 1
    tasa_ahorro = round(sum(ahorros) / total_ing * 100, 1)

    # Ranking de categorías: este mes contra el anterior
    def por_categoria(year, month):
        _, ult = calendar.monthrange(year, month)
        qs = Transaccion.objects.filter(
            usuario=request.user, tipo='EGRESO',
            fecha__gte=date(year, month, 1), fecha__lte=date(year, month, ult),
        ).values('categoria').annotate(total=Sum('monto'))
        return {x['categoria'] or 'Otros': float(x['total']) for x in qs}

    actual = por_categoria(hoy.year, hoy.month)
    anterior_f = date(hoy.year, hoy.month, 1) - relativedelta(months=1)
    anterior = por_categoria(anterior_f.year, anterior_f.month)
    maximo = max(actual.values()) if actual else 1
    etiquetas = dict(Transaccion.CATEGORIAS)

    ranking = []
    for cat, total in sorted(actual.items(), key=lambda x: -x[1]):
        antes = anterior.get(cat, 0)
        delta = round((total - antes) / antes * 100) if antes else None
        ranking.append({
            'nombre': cat,
            'label': etiquetas.get(cat, cat),
            'total': total,
            'ancho': round(total / maximo * 100),
            'delta': delta,
            'subio': delta is not None and delta > 0,
            'color': Transaccion.COLORES_CATEGORIA.get(cat, Transaccion.COLORES_CATEGORIA['Otros']),
        })

    context = {
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data_cuota),
        'data_restante_json': json.dumps(data_restante),
        'meses_json': json.dumps(meses),
        'ingresos_json': json.dumps(ingresos),
        'gastos_json': json.dumps(gastos),
        'promedio_gasto': round(promedio),
        'mejor_mes': meses[mejor] if mejor is not None else None,
        'mejor_ahorro': round(ahorros[mejor]) if mejor is not None else 0,
        'peor_mes': meses[peor] if peor is not None else None,
        'peor_gasto': round(gastos[peor]) if peor is not None else 0,
        'tasa_ahorro': tasa_ahorro,
        'ranking': ranking,
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/estadisticas.html', context)


# ============================================================
#  METAS
# ============================================================

@login_required(login_url='/login/')
def aportar_meta(request, meta_id):
    """Registra un aporte a una meta y actualiza su monto acumulado."""
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        monto = _monto_post(request)
        if monto <= 0:
            if es_ajax:
                return JsonResponse({'ok': False, 'msg': 'Ingresa un monto válido.'})
            messages.warning(request, 'Ingresa un monto válido.')
            return _redirigir(request)

        AporteMeta.objects.create(meta=meta, monto=monto, nota=request.POST.get('nota', ''))
        meta.monto_actual = (meta.monto_actual or 0) + monto
        meta.save(update_fields=['monto_actual'])

        if es_ajax:
            return JsonResponse({
                'ok': True, 'nombre': meta.nombre,
                'monto_actual': float(meta.monto_actual),
                'monto_meta': float(meta.monto_meta),
                'porcentaje': round(float(meta.porcentaje), 1),
                'completada': meta.esta_completa,
            })
        messages.success(request, f'Aporte a "{meta.nombre}" registrado.')

    return _redirigir(request)


@login_required(login_url='/login/')
def crear_meta(request):
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST)
        if form.is_valid():
            meta = form.save(commit=False)
            meta.usuario = request.user
            meta.save()
            messages.success(request, f"Meta '{meta.nombre}' creada.")
            return _redirigir(request)
    else:
        form = MetaAhorroForm()
    context = {'form': form}
    context.update(contadores(request.user))
    return render(request, 'finanzas/crear_meta.html', context)


@login_required(login_url='/login/')
def editar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST, instance=meta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Meta actualizada.')
            return _redirigir(request)
    else:
        form = MetaAhorroForm(instance=meta)
    context = {'form': form, 'editar': True, 'meta': meta}
    context.update(contadores(request.user))
    return render(request, 'finanzas/crear_meta.html', context)


@login_required(login_url='/login/')
def eliminar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        meta.delete()
        messages.success(request, 'Meta eliminada.')
    return _redirigir(request)


# ============================================================
#  PRÉSTAMOS (me deben)
# ============================================================

def _totales_prestamos(personas):
    return {
        'total_por_cobrar': round(sum(p.total_pendiente for p in personas)),
        'total_prestado': round(sum(p.total_prestado for p in personas)),
        'total_recuperado': round(sum(p.total_abonado for p in personas)),
    }


@login_required(login_url='/login/')
def prestamos(request):
    """Lista de personas que me deben, con su total pendiente.

    Ahora abre con la primera persona ya seleccionada a la derecha, para que
    la pantalla no arranque vacía.
    """
    personas = list(Persona.objects.filter(usuario=request.user)
                    .prefetch_related('prestamos__abonos'))

    seleccionada = None
    pedida = request.GET.get('persona')
    if pedida:
        seleccionada = next((p for p in personas if str(p.id) == str(pedida)), None)
    if seleccionada is None and personas:
        # La que más debe primero: es la que interesa ver.
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
    """Ver todos los préstamos de una persona y sus abonos.

    Pasa también la lista completa de personas para que la columna izquierda
    siga visible y se pueda cambiar de persona sin volver atrás.
    """
    persona = get_object_or_404(Persona, id=persona_id, usuario=request.user)
    personas = list(Persona.objects.filter(usuario=request.user)
                    .prefetch_related('prestamos__abonos'))

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
            return _redirigir(request, 'prestamos')

        persona = Persona.objects.create(usuario=request.user, nombre=nombre, contacto=contacto)
        messages.success(request, f'{nombre} agregado.')

        # Si vino con datos de préstamo, crearlo de una vez
        monto = _monto_post(request)
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
        monto = _monto_post(request)
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
    """Registra un pago que me hacen. NO afecta el balance del dashboard."""
    prestamo = get_object_or_404(Prestamo, id=prestamo_id, persona__usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        monto = _monto_post(request)
        if monto <= 0:
            if es_ajax:
                return JsonResponse({'ok': False, 'msg': 'Ingresa un monto válido.'})
            messages.warning(request, 'Ingresa un monto válido.')
            return redirect('detalle_persona', persona_id=prestamo.persona.id)

        # No permitir abonar más de lo que se debe: dejaba porcentajes sobre 100
        # y un pendiente negativo.
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


# ============================================================
#  ANÁLISIS
# ============================================================

def _simbolo_moneda(user):
    from .context_processors import CONFIG_MONEDA
    try:
        return CONFIG_MONEDA.get(user.profile.moneda, CONFIG_MONEDA['CLP'])['simbolo']
    except (AttributeError, KeyError, UserProfile.DoesNotExist):
        return '$'


@login_required(login_url='/login/')
def analisis_predictivo(request):
    """Análisis financiero: motor determinístico + interpretación IA opcional."""
    from .analisis import analizar_finanzas

    analisis = analizar_finanzas(request.user)
    circunferencia = 327  # 2*pi*52, el círculo de riesgo del SVG
    riesgo_offset = circunferencia - (circunferencia * analisis['riesgo_score'] / 100)

    context = {
        'analisis': analisis,
        'simbolo': _simbolo_moneda(request.user),
        'riesgo_offset': round(riesgo_offset, 1),
        'proy_meses_json': json.dumps([p['mes'] for p in analisis['proyeccion']]),
        'proy_deuda_json': json.dumps([p['deuda'] for p in analisis['proyeccion']]),
        'proy_pago_json': json.dumps([p['pago_mes'] for p in analisis['proyeccion']]),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/analisis.html', context)


@login_required(login_url='/login/')
def analisis_ia(request):
    """Endpoint AJAX: genera la interpretación con IA (puede tardar unos segundos)."""
    from .analisis import analizar_finanzas
    from .ia import interpretar_con_ia

    analisis = analizar_finanzas(request.user)
    interpretacion = interpretar_con_ia(analisis, _simbolo_moneda(request.user))
    if interpretacion:
        return JsonResponse({'ok': True, 'ia': interpretacion})
    return JsonResponse({'ok': False, 'msg': 'IA no disponible'})


# ============================================================
#  GASTOS PENDIENTES
# ============================================================

@login_required(login_url='/login/')
def crear_gasto_pendiente(request):
    """Crea un gasto pendiente. Genera de inmediato la transacción de gasto
    con fecha = vencimiento, para que cuente en el mes que corresponde.
    Marcarlo pagado luego NO vuelve a sumar (evita doble conteo)."""
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        monto = _monto_post(request)
        fecha_venc = request.POST.get('fecha_vencimiento')
        categoria = request.POST.get('categoria', 'Cuentas').strip() or 'Cuentas'

        if not (nombre and monto > 0 and fecha_venc):
            messages.warning(request, 'Completa nombre, monto y fecha.')
            return _redirigir(request)

        try:
            venc = datetime.strptime(fecha_venc, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.warning(request, 'La fecha no es válida.')
            return _redirigir(request)

        tx = Transaccion.objects.create(
            usuario=request.user, tipo='EGRESO', monto=monto,
            categoria=categoria, descripcion=f'Pendiente: {nombre}',
            fecha=venc, es_cuota=False,
        )
        GastoPendiente.objects.create(
            usuario=request.user, nombre=nombre, monto=monto,
            fecha_vencimiento=venc, categoria=categoria, transaccion=tx,
        )
        messages.success(request, 'Gasto pendiente agregado y contabilizado.')
        return _redirigir(request)

    context = {}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_gasto_pendiente.html', context)


@login_required(login_url='/login/')
def pagar_gasto_pendiente(request, gasto_id):
    """Marca un gasto pendiente como pagado. NO crea transacción:
    ya se creó al crear el gasto, así que solo cambia el estado."""
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and not gasto.pagado:
        gasto.pagado = True
        gasto.fecha_pago = date.today()
        gasto.save(update_fields=['pagado', 'fecha_pago'])
        if es_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, f'{gasto.nombre} marcado como pagado.')
    return _redirigir(request)


@login_required(login_url='/login/')
def anular_gasto_pendiente(request, gasto_id):
    """Revierte el estado 'pagado' del gasto. La transacción NO se toca:
    el gasto sigue contabilizado esté pagado o no."""
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and gasto.pagado:
        gasto.pagado = False
        gasto.fecha_pago = None
        gasto.save(update_fields=['pagado', 'fecha_pago'])
        if es_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, 'Marcado como no pagado.')
    return _redirigir(request)


@login_required(login_url='/login/')
def eliminar_gasto_pendiente(request, gasto_id):
    """Elimina el gasto pendiente Y su transacción asociada (deja de contar)."""
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    if request.method == 'POST':
        if gasto.transaccion:
            gasto.transaccion.delete()
        gasto.delete()
        messages.success(request, 'Gasto pendiente eliminado.')
    return _redirigir(request)


# ============================================================
#  SUSCRIPCIONES
# ============================================================

@login_required(login_url='/login/')
def suscripciones(request):
    """Lista de suscripciones (activas e inactivas)."""
    subs = list(Suscripcion.objects.filter(usuario=request.user))
    activas = [s for s in subs if s.activa]
    total_mensual = sum(float(s.monto) for s in activas)

    # Aviso de servicios que se pisan (dos de música, dos de video...).
    # Es el insight que más ahorra y no requiere IA.
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
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/suscripciones.html', context)


@login_required(login_url='/login/')
def crear_suscripcion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        monto = _monto_post(request)
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
def cancelar_suscripcion(request, sub_id):
    """Cancela una suscripción (deja de generar cobros). No borra el historial."""
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
            # Se retoma desde el mes actual, para no generar de golpe los
            # cobros de todos los meses que estuvo cancelada.
            hoy = date.today()
            sub.ultimo_mes_generado = hoy.year * 100 + hoy.month - 1
            sub.save(update_fields=['activa', 'fecha_cancelada', 'ultimo_mes_generado'])
            generar_cobros_suscripciones(request.user)
            messages.success(request, f'{sub.nombre} reactivada.')
    return redirect('suscripciones')


@login_required(login_url='/login/')
def eliminar_suscripcion(request, sub_id):
    """Elimina la suscripción por completo (el historial de gastos se mantiene)."""
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    if request.method == 'POST':
        sub.delete()
        messages.success(request, 'Suscripción eliminada.')
    return redirect('suscripciones')


# ============================================================
#  REGISTRO Y ONBOARDING
# ============================================================

def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # get_or_create evita el IntegrityError si ya existe un perfil
            # (por ejemplo si hay una señal post_save que lo crea).
            profile, _ = UserProfile.objects.get_or_create(usuario=user)
            profile.nombre_completo = request.POST.get('nombre_completo', '').strip()
            profile.email = request.POST.get('email_perfil', '').strip()
            profile.save()
            return redirect('onboarding')
    else:
        form = UserCreationForm()
    return render(request, 'registration/registro.html', {'form': form})


@login_required(login_url='/login/')
def onboarding(request):
    profile = get_or_create_profile(request.user)
    if profile.onboarding_completado:
        return redirect('dashboard')
    return render(request, 'finanzas/onboarding.html', {'profile': profile})


@login_required(login_url='/login/')
def completar_onboarding(request):
    if request.method != 'POST':
        return redirect('dashboard')

    ingreso_monto = _monto_post(request, 'ingreso_monto')
    if ingreso_monto > 0:
        Transaccion.objects.create(
            usuario=request.user, tipo='INGRESO', monto=ingreso_monto,
            categoria='Sueldo',  # antes 'Otros': el sueldo es la categoría real
            descripcion=request.POST.get('ingreso_desc') or 'Ingreso mensual',
            fecha=timezone.localdate(),
        )

    acreedor = request.POST.get('deuda_acreedor', '').strip()
    deuda_monto = _monto_post(request, 'deuda_monto')
    if acreedor and deuda_monto > 0:
        try:
            cuotas = max(1, int(request.POST.get('deuda_cuotas', 1)))
        except (ValueError, TypeError):
            cuotas = 1
        Deuda.objects.create(
            usuario=request.user, acreedor=acreedor,
            monto_total=deuda_monto, cuotas_totales=cuotas,
            fecha_inicio=timezone.localdate(),
        )

    presupuesto_val = _monto_post(request, 'presupuesto')
    if presupuesto_val > 0:
        p, _ = Presupuesto.objects.get_or_create(
            usuario=request.user, defaults={'limite_mensual': presupuesto_val})
        p.limite_mensual = presupuesto_val
        p.save(update_fields=['limite_mensual'])

    profile = get_or_create_profile(request.user)
    profile.onboarding_completado = True
    profile.save(update_fields=['onboarding_completado'])
    messages.success(request, f'Listo, {profile.nombre_display}. Tu mes ya está armado.')
    return redirect('dashboard')


# ============================================================
#  PERFIL
# ============================================================

class PerfilForm(forms.ModelForm):
    """Antes se definía dentro de la vista, así que se reconstruía en cada
    request y no se podía importar desde otro módulo."""
    class Meta:
        model = UserProfile
        fields = ['nombre_completo', 'email', 'telefono', 'ciudad', 'pais', 'moneda']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'placeholder': 'Ej: Juan Pérez'}),
            'email':           forms.EmailInput(attrs={'placeholder': 'Ej: juan@email.com'}),
            'telefono':        forms.TextInput(attrs={'placeholder': 'Ej: +56 9 1234 5678'}),
            'ciudad':          forms.TextInput(attrs={'placeholder': 'Ej: Santiago'}),
            'pais':            forms.TextInput(attrs={'placeholder': 'Ej: Chile'}),
            'moneda':          forms.Select(),
        }


@login_required(login_url='/login/')
def perfil(request):
    profile = get_or_create_profile(request.user)
    pw_form = PasswordChangeForm(request.user)
    perfil_form = PerfilForm(instance=profile)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'perfil':
            perfil_form = PerfilForm(request.POST, instance=profile)
            if perfil_form.is_valid():
                perfil_form.save()
                nombre = perfil_form.cleaned_data.get('nombre_completo', '').strip()
                if nombre:
                    partes = nombre.split(' ', 1)
                    request.user.first_name = partes[0]
                    request.user.last_name = partes[1] if len(partes) > 1 else ''
                    request.user.save(update_fields=['first_name', 'last_name'])
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('perfil')
        elif accion == 'password':
            pw_form = PasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                user = pw_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Contraseña actualizada.')
                return redirect('perfil')

    context = {
        'perfil_form': perfil_form, 'pw_form': pw_form, 'profile': profile,
        'total_trans': Transaccion.objects.filter(usuario=request.user).count(),
        'total_deudas': Deuda.objects.filter(usuario=request.user).count(),
        'miembro_desde': request.user.date_joined.strftime('%B %Y'),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/perfil.html', context)


# ============================================================
#  EXPORTAR
# ============================================================

@login_required(login_url='/login/')
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Mis_Finanzas.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Fecha', 'Tipo', 'Categoria', 'Descripcion', 'Monto ($)'])
    for t in Transaccion.objects.filter(usuario=request.user).order_by('-fecha'):
        writer.writerow([t.fecha.strftime('%d/%m/%Y'), t.get_tipo_display(),
                         t.categoria, t.descripcion, int(t.monto)])
    return response
