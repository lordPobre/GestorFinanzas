import csv
import calendar
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from dateutil.relativedelta import relativedelta
from django.db.models import F
from django.http import HttpResponse
from collections import defaultdict
from django.utils import timezone
from datetime import date
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from .models import Transaccion, Deuda, Presupuesto, MetaAhorro, AporteMeta, Persona, Prestamo, AbonoPrestamo, GastoPendiente, Suscripcion
from .forms import DeudaForm, TransaccionForm, MetaAhorroForm

def generar_cobros_suscripciones(usuario):
    """Genera los cobros mensuales de suscripciones activas que falten.
    Se llama al abrir el dashboard (generación perezosa).
    Cada cobro se registra como gasto del mes (transacción EGRESO)."""
    from dateutil.relativedelta import relativedelta
    import calendar as _cal
    hoy = date.today()
    mes_actual_clave = hoy.year * 100 + hoy.month

    for sub in Suscripcion.objects.filter(usuario=usuario, activa=True):
        if sub.ultimo_mes_generado == 0:
            cursor = date(sub.fecha_inicio.year, sub.fecha_inicio.month, 1)
        else:
            ultimo_anio = sub.ultimo_mes_generado // 100
            ultimo_mes = sub.ultimo_mes_generado % 100
            cursor = date(ultimo_anio, ultimo_mes, 1) + relativedelta(months=1)

        while cursor.year * 100 + cursor.month <= mes_actual_clave:
            _, ult_dia = _cal.monthrange(cursor.year, cursor.month)
            dia = min(sub.dia_cobro, ult_dia)
            Transaccion.objects.create(
                usuario=usuario, tipo='EGRESO', monto=sub.monto,
                categoria=sub.categoria or 'Suscripciones',
                descripcion=f'Suscripción: {sub.nombre}',
                fecha=date(cursor.year, cursor.month, dia), es_cuota=False,
            )
            sub.ultimo_mes_generado = cursor.year * 100 + cursor.month
            cursor = cursor + relativedelta(months=1)
        sub.save()

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

    if month == 1: prev_month, prev_year = 12, year - 1
    else: prev_month, prev_year = month - 1, year
    if month == 12: next_month, next_year = 1, year + 1
    else: next_month, next_year = month + 1, year

    _, ultimo_dia = calendar.monthrange(year, month)
    fecha_inicio = date(year, month, 1)
    fecha_fin = date(year, month, ultimo_dia)
    nombre_mes = date(year, month, 1).strftime('%B %Y').capitalize()

    total_ingresos = Transaccion.objects.filter(
        usuario=request.user, tipo='INGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(total=Sum('monto'))['total'] or 0

    # Gastos manuales (excluye pagos automáticos de cuotas vía es_cuota)
    total_gastos = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin,
        es_cuota=False,
    ).aggregate(total=Sum('monto'))['total'] or 0

    todas_las_deudas = Deuda.objects.filter(usuario=request.user)
    deudas_del_mes = []
    cuotas_pagadas_mes = 0.0
    cuotas_pendientes_mes = 0.0
    eventos_mes = {}

    for d in todas_las_deudas:
        dia_venc = d.fecha_inicio.day
        if dia_venc > ultimo_dia: dia_venc = ultimo_dia
        fecha_cobro = date(year, month, dia_venc)
        fecha_fin_deuda = d.fecha_inicio + relativedelta(months=int(d.cuotas_totales) - 1)
        if not (d.fecha_inicio <= fecha_cobro <= fecha_fin_deuda): continue
        deudas_del_mes.append(d)

        if year < hoy.year or (year == hoy.year and month < hoy.month): estado = 'pagado'
        elif year > hoy.year or (year == hoy.year and month > hoy.month): estado = 'pendiente'
        else:
            if d.proximo_vencimiento and d.proximo_vencimiento > fecha_cobro: estado = 'pagado'
            elif d.cuotas_pagadas >= d.cuotas_totales: estado = 'pagado'
            else: estado = 'pendiente'

        monto_cuota = float(d.monto_cuota)
        if estado == 'pagado': cuotas_pagadas_mes += monto_cuota
        else: cuotas_pendientes_mes += monto_cuota

        if dia_venc not in eventos_mes: eventos_mes[dia_venc] = []
        eventos_mes[dia_venc].append({'deuda': d, 'estado': estado, 'monto': d.monto_cuota})

    total_cuotas_mes = cuotas_pagadas_mes + cuotas_pendientes_mes

    # RESUMEN: gastos manuales del día a día solamente
    ya_gaste = float(total_gastos)
    # Total comprometido = gastos + cuotas del mes completo
    total_comprometido_mes = float(total_gastos) + total_cuotas_mes
    # Disponible = ingresos - gastos - cuotas completas
    disponible = float(total_ingresos) - total_comprometido_mes

    cal = calendar.monthcalendar(year, month)
    calendario_datos = []
    for semana in cal:
        semana_datos = []
        for dia in semana:
            if dia == 0: semana_datos.append(None)
            else:
                semana_datos.append({
                    'numero': dia,
                    'es_hoy': (dia == hoy.day and month == hoy.month and year == hoy.year),
                    'eventos': eventos_mes.get(dia, [])
                })
        calendario_datos.append(semana_datos)

    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = [], [], [], []
    nombres_meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        _, ult = calendar.monthrange(f.year, f.month)
        fi, ff = date(f.year, f.month, 1), date(f.year, f.month, ult)

        ing = float(Transaccion.objects.filter(
            usuario=request.user, tipo='INGRESO', fecha__gte=fi, fecha__lte=ff
        ).aggregate(t=Sum('monto'))['t'] or 0)

        gas = float(Transaccion.objects.filter(
            usuario=request.user, tipo='EGRESO',
            fecha__gte=fi, fecha__lte=ff, es_cuota=False,
        ).aggregate(t=Sum('monto'))['t'] or 0)

        cuotas_m = 0.0
        for d in todas_las_deudas:
            dv = d.fecha_inicio.day
            if dv > ult: dv = ult
            fc = date(f.year, f.month, dv)
            ffd = d.fecha_inicio + relativedelta(months=int(d.cuotas_totales) - 1)
            if d.fecha_inicio <= fc <= ffd: cuotas_m += float(d.monto_cuota)

        meses_labels.append(f"{nombres_meses[f.month-1]} {f.year}")
        datos_ingresos.append(ing)
        datos_gastos.append(gas)
        datos_cuotas.append(cuotas_m)

    gastos_categoria = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).values('categoria').annotate(total=Sum('monto')).order_by('-total')

    ultimas = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]
    deuda_total = sum(float(d.monto_restante) for d in todas_las_deudas.filter(cuotas_pagadas__lt=F('cuotas_totales')))
    metas = MetaAhorro.objects.filter(usuario=request.user)
    es_nuevo = (total_ingresos == 0 and total_gastos == 0 and not todas_las_deudas.exists())
    profile = get_or_create_profile(request.user)

    # ========== INSIGHTS Y PROYECCIONES ==========
    insights = []

    # --- 1. Presupuesto: alerta si el gasto se acerca o supera el límite ---
    presupuesto = Presupuesto.objects.filter(usuario=request.user).first()
    presupuesto_pct = None
    if presupuesto and presupuesto.limite_mensual > 0:
        gasto_vs_presupuesto = float(total_gastos)
        limite = float(presupuesto.limite_mensual)
        presupuesto_pct = round((gasto_vs_presupuesto / limite) * 100)
        if presupuesto_pct >= 100:
            insights.append({
                'tipo': 'peligro', 'icono': 'fa-exclamation-triangle',
                'texto': f'Superaste tu presupuesto mensual ({presupuesto_pct}%). Llevas gastado más de lo planeado.'
            })
        elif presupuesto_pct >= 80:
            insights.append({
                'tipo': 'alerta', 'icono': 'fa-exclamation-triangle',
                'texto': f'Vas en el {presupuesto_pct}% de tu presupuesto. Cuida los gastos del resto del mes.'
            })

    # --- 2. Comparación con el mes anterior (gastos) ---
    # datos_gastos tiene los últimos 6 meses; el penúltimo es el mes anterior
    if len(datos_gastos) >= 2:
        gasto_actual = datos_gastos[-1]
        gasto_anterior = datos_gastos[-2]
        if gasto_anterior > 0:
            variacion = round(((gasto_actual - gasto_anterior) / gasto_anterior) * 100)
            if variacion >= 20:
                insights.append({
                    'tipo': 'alerta', 'icono': 'fa-arrow-up',
                    'texto': f'Gastaste {variacion}% más que el mes pasado.'
                })
            elif variacion <= -20:
                insights.append({
                    'tipo': 'exito', 'icono': 'fa-arrow-down',
                    'texto': f'Gastaste {abs(variacion)}% menos que el mes pasado. ¡Bien!'
                })

    # --- 3. Deudas próximas a vencer (usa la property urgencia) ---
    deudas_urgentes = []
    for d in todas_las_deudas:
        if d.cuotas_pagadas >= d.cuotas_totales:
            continue
        urgencia = d.urgencia
        dias = d.dias_para_vencer
        if urgencia in ('vencida', 'critica') and dias is not None:
            deudas_urgentes.append({'deuda': d, 'dias': dias, 'urgencia': urgencia})
    # Ordenar por más urgente primero
    deudas_urgentes.sort(key=lambda x: x['dias'])
    for du in deudas_urgentes[:2]:  # máximo 2 alertas
        d, dias = du['deuda'], du['dias']
        if dias < 0:
            insights.append({
                'tipo': 'peligro', 'icono': 'fa-credit-card',
                'texto': f'La cuota de {d.acreedor} está vencida hace {abs(dias)} día{"s" if abs(dias) != 1 else ""}.'
            })
        else:
            insights.append({
                'tipo': 'alerta', 'icono': 'fa-credit-card',
                'texto': f'La cuota de {d.acreedor} vence en {dias} día{"s" if dias != 1 else ""}.'
            })

    # --- 4. Proyección: cuándo se termina cada deuda ---
    proyecciones_deuda = []
    for d in todas_las_deudas.filter(cuotas_pagadas__lt=F('cuotas_totales')):
        fecha_fin = d.fecha_fin_estimada
        cuotas_restantes = d.cuotas_totales - d.cuotas_pagadas
        proyecciones_deuda.append({
            'acreedor': d.acreedor,
            'fecha_fin': fecha_fin,
            'cuotas_restantes': cuotas_restantes,
            'mes_fin': nombres_meses[fecha_fin.month - 1] + ' ' + str(fecha_fin.year),
        })
    # La deuda que se termina primero
    if proyecciones_deuda:
        proyecciones_deuda.sort(key=lambda x: x['fecha_fin'])
        prox = proyecciones_deuda[0]
        insights.append({
            'tipo': 'info', 'icono': 'fa-check-circle',
            'texto': f'A este ritmo, terminas de pagar {prox["acreedor"]} en {prox["mes_fin"]}.'
        })

    context = {
        'nombre_mes': nombre_mes,
        'profile': profile,
        'es_nuevo': es_nuevo,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
        'total_ingresos': round(float(total_ingresos), 0),
        'total_gastos': round(float(total_gastos), 0),
        'total_cuotas_mes': round(total_cuotas_mes, 0),
        'cuotas_pagadas_mes': round(cuotas_pagadas_mes, 0),
        'cuotas_pendientes_mes': round(cuotas_pendientes_mes, 0),
        'ya_gaste': round(ya_gaste, 0),
        'total_comprometido_mes': round(total_comprometido_mes, 0),
        'disponible': round(disponible, 0),
        'deuda_total': round(deuda_total, 0),
        'insights': insights,
        'presupuesto': presupuesto,
        'presupuesto_pct': presupuesto_pct,
        'proyecciones_deuda': proyecciones_deuda,
        'deudas': deudas_del_mes,
        'gastos_pendientes': GastoPendiente.objects.filter(usuario=request.user, pagado=False),
        'ultimas': ultimas,
        'metas': metas,
        'calendario': calendario_datos,
        'meses_json': json.dumps(meses_labels),
        'ingresos_json': json.dumps(datos_ingresos),
        'gastos_json': json.dumps(datos_gastos),
        'cuotas_json': json.dumps(datos_cuotas),
        'cat_labels_json': json.dumps([x['categoria'] or 'Otros' for x in gastos_categoria]),
        'cat_data_json': json.dumps([float(x['total']) for x in gastos_categoria]),
    }
    return render(request, 'finanzas/dashboard.html', context)


@login_required(login_url='/login/')
def pagar_cuota(request, deuda_id):
    from django.http import JsonResponse
    if request.method == 'POST':
        deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
        es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if deuda.cuotas_pagadas < deuda.cuotas_totales:
            deuda.cuotas_pagadas += 1
            deuda.save()
            Transaccion.objects.create(
                usuario=request.user, tipo='EGRESO',
                monto=deuda.monto_cuota, categoria=deuda.categoria,
                descripcion=f'Cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} — {deuda.acreedor}',
                fecha=timezone.now(),
                es_cuota=True,
            )
            if es_ajax:
                return JsonResponse({'ok': True, 'acreedor': deuda.acreedor,
                    'cuotas_pagadas': deuda.cuotas_pagadas, 'cuotas_totales': deuda.cuotas_totales,
                    'porcentaje': deuda.porcentaje, 'terminada': deuda.cuotas_pagadas >= deuda.cuotas_totales,
                    'monto': str(deuda.monto_cuota)})
            messages.success(request, f'Cuota de {deuda.acreedor} registrada.')
        else:
            if es_ajax: return JsonResponse({'ok': False, 'msg': 'Ya está pagada.'})
            messages.warning(request, f'{deuda.acreedor} ya está pagada.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def anular_cuota(request, deuda_id):
    from django.http import JsonResponse
    if request.method == 'POST':
        deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
        es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if deuda.cuotas_pagadas > 0:
            deuda.cuotas_pagadas -= 1
            deuda.save()
            ultima = Transaccion.objects.filter(
                usuario=request.user, tipo='EGRESO',
                es_cuota=True, descripcion__icontains=deuda.acreedor
            ).order_by('-fecha', '-id').first()
            if ultima: ultima.delete()
            if es_ajax:
                return JsonResponse({'ok': True, 'acreedor': deuda.acreedor,
                    'cuotas_pagadas': deuda.cuotas_pagadas, 'cuotas_totales': deuda.cuotas_totales,
                    'porcentaje': deuda.porcentaje})
            messages.success(request, f'Pago de {deuda.acreedor} anulado.')
        else:
            if es_ajax: return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
            messages.warning(request, 'No hay pagos que anular.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def crear_deuda(request):
    if request.method == 'POST':
        form = DeudaForm(request.POST)
        if form.is_valid():
            deuda = form.save(commit=False)
            deuda.usuario = request.user
            deuda.save()
            messages.success(request, f"Deuda '{deuda.acreedor}' agregada.")
            return redirect('dashboard')
    else:
        form = DeudaForm()
    return render(request, 'finanzas/form_deuda.html', {'form': form})


@login_required(login_url='/login/')
def editar_deuda(request, deuda_id):
    deuda = get_object_or_404(Deuda, id=deuda_id, usuario=request.user)
    if request.method == 'POST':
        form = DeudaForm(request.POST, instance=deuda)
        if form.is_valid():
            form.save()
            messages.success(request, 'Deuda actualizada.')
            return redirect('dashboard')
    else:
        form = DeudaForm(instance=deuda)
    return render(request, 'finanzas/form_deuda.html', {'form': form, 'editar': True, 'deuda': deuda})


@login_required(login_url='/login/')
def eliminar_deuda(request, deuda_id):
    deuda = get_object_or_404(Deuda, id=deuda_id, usuario=request.user)
    if request.method == 'POST':
        nombre = deuda.acreedor
        deuda.delete()
        messages.success(request, f"Deuda '{nombre}' eliminada.")
    return redirect('dashboard')


@login_required(login_url='/login/')
def registrar_transaccion(request):
    tipo_inicial = request.GET.get('tipo', 'INGRESO')
    if request.method == 'POST':
        form = TransaccionForm(request.POST)
        if form.is_valid():
            t = form.save(commit=False)
            t.usuario = request.user
            t.save()
            messages.success(request, f'{"Ingreso" if t.tipo == "INGRESO" else "Gasto"} registrado.')
            return redirect('dashboard')
    else:
        form = TransaccionForm(initial={'tipo': tipo_inicial})
    return render(request, 'finanzas/form_transaccion.html', {'form': form, 'tipo_inicial': tipo_inicial})


@login_required(login_url='/login/')
def editar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=t)
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimiento actualizado.')
            return redirect('dashboard')
    else:
        form = TransaccionForm(instance=t)
    return render(request, 'finanzas/form_transaccion.html', {'form': form, 'editar': True, 'tipo_inicial': t.tipo})


@login_required(login_url='/login/')
def eliminar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        t.delete()
        messages.success(request, 'Movimiento eliminado.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def estadisticas(request):
    deudas = Deuda.objects.filter(usuario=request.user, cuotas_pagadas__lt=F('cuotas_totales'))
    labels, data_cuota, data_restante = [], [], []
    for d in deudas:
        labels.append(d.acreedor)
        data_cuota.append(float(d.monto_cuota))
        data_restante.append(float(d.monto_restante))
    return render(request, 'finanzas/estadisticas.html', {
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data_cuota),
        'data_restante_json': json.dumps(data_restante),
    })


def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            UserProfile.objects.create(
                usuario=user,
                nombre_completo=request.POST.get('nombre_completo', '').strip(),
                email=request.POST.get('email_perfil', '').strip(),
            )
            return redirect('onboarding')
    else:
        form = UserCreationForm()
    return render(request, 'registration/registro.html', {'form': form})


@login_required(login_url='/login/')
def aportar_meta(request, meta_id):
    """Registra un aporte a una meta y actualiza su monto acumulado."""
    from django.http import JsonResponse
    from decimal import Decimal, InvalidOperation

    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        monto_raw = request.POST.get('monto', '0')
        try:
            monto = Decimal(str(monto_raw))
        except (InvalidOperation, ValueError):
            monto = Decimal('0')

        if monto <= 0:
            if es_ajax:
                return JsonResponse({'ok': False, 'msg': 'Ingresa un monto válido.'})
            messages.warning(request, 'Ingresa un monto válido.')
            return redirect('dashboard')

        # Registrar el aporte y sumar al acumulado
        AporteMeta.objects.create(meta=meta, monto=monto, nota=request.POST.get('nota', ''))
        meta.monto_actual = (meta.monto_actual or 0) + monto
        meta.save()

        completada = meta.monto_actual >= meta.monto_meta
        if es_ajax:
            return JsonResponse({
                'ok': True,
                'nombre': meta.nombre,
                'monto_actual': float(meta.monto_actual),
                'monto_meta': float(meta.monto_meta),
                'porcentaje': round(float(meta.porcentaje), 1),
                'completada': completada,
            })
        messages.success(request, f'Aporte a "{meta.nombre}" registrado.')

    return redirect('dashboard')


@login_required(login_url='/login/')
def crear_meta(request):
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST)
        if form.is_valid():
            meta = form.save(commit=False)
            meta.usuario = request.user
            meta.save()
            messages.success(request, f"Meta '{meta.nombre}' creada.")
            return redirect('dashboard')
    else:
        form = MetaAhorroForm()
    return render(request, 'finanzas/crear_meta.html', {'form': form})


@login_required(login_url='/login/')
def editar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST, instance=meta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Meta actualizada.')
            return redirect('dashboard')
    else:
        form = MetaAhorroForm(instance=meta)
    return render(request, 'finanzas/crear_meta.html', {'form': form, 'editar': True, 'meta': meta})


@login_required(login_url='/login/')
def eliminar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        meta.delete()
        messages.success(request, 'Meta eliminada.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def prestamos(request):
    """Lista de personas que me deben, con su total pendiente."""
    personas = Persona.objects.filter(usuario=request.user)
    # Totales generales
    total_por_cobrar = sum(p.total_pendiente for p in personas)
    total_prestado = sum(p.total_prestado for p in personas)
    total_recuperado = sum(p.total_abonado for p in personas)
    return render(request, 'finanzas/prestamos.html', {
        'personas': personas,
        'total_por_cobrar': round(total_por_cobrar, 0),
        'total_prestado': round(total_prestado, 0),
        'total_recuperado': round(total_recuperado, 0),
    })


@login_required(login_url='/login/')
def detalle_persona(request, persona_id):
    """Ver todos los préstamos de una persona y sus abonos."""
    persona = get_object_or_404(Persona, id=persona_id, usuario=request.user)
    prestamos_lista = persona.prestamos.all()
    return render(request, 'finanzas/detalle_persona.html', {
        'persona': persona,
        'prestamos': prestamos_lista,
    })


@login_required(login_url='/login/')
def crear_persona(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        contacto = request.POST.get('contacto', '').strip()
        if nombre:
            persona = Persona.objects.create(usuario=request.user, nombre=nombre, contacto=contacto)
            messages.success(request, f'{nombre} agregado.')
            # Si vino con datos de préstamo, crearlo de una vez
            monto = request.POST.get('monto')
            if monto:
                try:
                    tipo = request.POST.get('tipo', 'UNICO')
                    cuotas = int(request.POST.get('cuotas_totales', 1)) if tipo == 'CUOTAS' else 1
                    Prestamo.objects.create(
                        persona=persona,
                        descripcion=request.POST.get('descripcion', 'Préstamo').strip() or 'Préstamo',
                        monto=float(monto), tipo=tipo, cuotas_totales=max(1, cuotas),
                    )
                except (ValueError, TypeError):
                    pass
            return redirect('detalle_persona', persona_id=persona.id)
        messages.warning(request, 'Ingresa un nombre.')
    return render(request, 'finanzas/form_persona.html', {})


@login_required(login_url='/login/')
def crear_prestamo(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id, usuario=request.user)
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion', '').strip()
        monto = request.POST.get('monto')
        if descripcion and monto:
            try:
                tipo = request.POST.get('tipo', 'UNICO')
                cuotas = int(request.POST.get('cuotas_totales', 1)) if tipo == 'CUOTAS' else 1
                Prestamo.objects.create(
                    persona=persona, descripcion=descripcion,
                    monto=float(monto), tipo=tipo, cuotas_totales=max(1, cuotas),
                )
                messages.success(request, 'Préstamo agregado.')
                return redirect('detalle_persona', persona_id=persona.id)
            except (ValueError, TypeError):
                messages.warning(request, 'Revisa el monto ingresado.')
    return render(request, 'finanzas/form_prestamo.html', {'persona': persona})


@login_required(login_url='/login/')
def abonar_prestamo(request, prestamo_id):
    """Registra un pago que me hacen. NO afecta el balance del dashboard."""
    from django.http import JsonResponse
    from decimal import Decimal, InvalidOperation

    prestamo = get_object_or_404(Prestamo, id=prestamo_id, persona__usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        try:
            monto = Decimal(str(request.POST.get('monto', '0')))
        except (InvalidOperation, ValueError):
            monto = Decimal('0')

        if monto <= 0:
            if es_ajax:
                return JsonResponse({'ok': False, 'msg': 'Ingresa un monto válido.'})
            messages.warning(request, 'Ingresa un monto válido.')
            return redirect('detalle_persona', persona_id=prestamo.persona.id)

        AbonoPrestamo.objects.create(prestamo=prestamo, monto=monto, nota=request.POST.get('nota', ''))

        if es_ajax:
            return JsonResponse({
                'ok': True,
                'pendiente': prestamo.monto_pendiente,
                'porcentaje': prestamo.porcentaje,
                'pagado': prestamo.esta_pagado,
            })
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
    return redirect('prestamos')


@login_required(login_url='/login/')
def eliminar_prestamo(request, prestamo_id):
    prestamo = get_object_or_404(Prestamo, id=prestamo_id, persona__usuario=request.user)
    persona_id = prestamo.persona.id
    if request.method == 'POST':
        prestamo.delete()
        messages.success(request, 'Préstamo eliminado.')
    return redirect('detalle_persona', persona_id=persona_id)


@login_required(login_url='/login/')
def analisis_predictivo(request):
    """Análisis financiero: motor determinístico + interpretación IA opcional."""
    from .analisis import analizar_finanzas
    from .ia import interpretar_con_ia
    from .context_processors import CONFIG_MONEDA

    analisis = analizar_finanzas(request.user)

    # Símbolo de moneda del usuario
    try:
        moneda_cod = request.user.profile.moneda
        simbolo = CONFIG_MONEDA.get(moneda_cod, CONFIG_MONEDA['CLP'])['simbolo']
    except Exception:
        simbolo = '$'

    # Cálculo del offset del círculo de riesgo (SVG): circunferencia = 2*pi*52 ≈ 327
    circunferencia = 327
    riesgo_offset = circunferencia - (circunferencia * analisis['riesgo_score'] / 100)

    # Datos de proyección para el gráfico
    import json as _json
    proy_meses = [p['mes'] for p in analisis['proyeccion']]
    proy_deuda = [p['deuda'] for p in analisis['proyeccion']]
    proy_pago = [p['pago_mes'] for p in analisis['proyeccion']]

    # La interpretación con IA se pide vía AJAX aparte (para no bloquear la carga)
    return render(request, 'finanzas/analisis.html', {
        'analisis': analisis,
        'simbolo': simbolo,
        'riesgo_offset': round(riesgo_offset, 1),
        'proy_meses_json': _json.dumps(proy_meses),
        'proy_deuda_json': _json.dumps(proy_deuda),
        'proy_pago_json': _json.dumps(proy_pago),
    })


@login_required(login_url='/login/')
def analisis_ia(request):
    """Endpoint AJAX: genera la interpretación con IA (puede tardar unos segundos)."""
    from django.http import JsonResponse
    from .analisis import analizar_finanzas
    from .ia import interpretar_con_ia
    from .context_processors import CONFIG_MONEDA

    analisis = analizar_finanzas(request.user)
    try:
        moneda_cod = request.user.profile.moneda
        simbolo = CONFIG_MONEDA.get(moneda_cod, CONFIG_MONEDA['CLP'])['simbolo']
    except Exception:
        simbolo = '$'

    interpretacion = interpretar_con_ia(analisis, simbolo)
    if interpretacion:
        return JsonResponse({'ok': True, 'ia': interpretacion})
    return JsonResponse({'ok': False, 'msg': 'IA no disponible'})


@login_required(login_url='/login/')
def crear_gasto_pendiente(request):
    """Crea un gasto pendiente. Genera de inmediato la transacción de gasto
    con fecha = vencimiento, para que cuente en el mes que corresponde.
    Marcarlo pagado luego NO vuelve a sumar (evita doble conteo)."""
    from datetime import datetime
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        monto = request.POST.get('monto')
        fecha_venc = request.POST.get('fecha_vencimiento')
        categoria = request.POST.get('categoria', 'Cuentas').strip() or 'Cuentas'
        if nombre and monto and fecha_venc:
            try:
                venc = datetime.strptime(fecha_venc, '%Y-%m-%d').date()
                monto_f = float(monto)
                # 1. Crear la transacción de gasto en el mes de vencimiento
                tx = Transaccion.objects.create(
                    usuario=request.user, tipo='EGRESO', monto=monto_f,
                    categoria=categoria, descripcion=f'Pendiente: {nombre}',
                    fecha=venc, es_cuota=False,
                )
                # 2. Crear el gasto pendiente vinculado a esa transacción
                GastoPendiente.objects.create(
                    usuario=request.user, nombre=nombre, monto=monto_f,
                    fecha_vencimiento=venc, categoria=categoria, transaccion=tx,
                )
                messages.success(request, 'Gasto pendiente agregado y contabilizado.')
            except (ValueError, TypeError):
                messages.warning(request, 'Revisa los datos ingresados.')
            return redirect('dashboard')
        messages.warning(request, 'Completa nombre, monto y fecha.')
    return render(request, 'finanzas/form_gasto_pendiente.html', {})


@login_required(login_url='/login/')
def pagar_gasto_pendiente(request, gasto_id):
    """Marca un gasto pendiente como pagado. NO crea transacción:
    ya se creó al crear el gasto, así que solo cambia el estado."""
    from django.http import JsonResponse
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and not gasto.pagado:
        gasto.pagado = True
        gasto.fecha_pago = date.today()
        gasto.save()
        if es_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, f'{gasto.nombre} marcado como pagado.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def anular_gasto_pendiente(request, gasto_id):
    """Revierte el estado 'pagado' del gasto. La transacción NO se toca:
    el gasto sigue contabilizado esté pagado o no."""
    from django.http import JsonResponse
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST' and gasto.pagado:
        gasto.pagado = False
        gasto.fecha_pago = None
        gasto.save()
        if es_ajax:
            return JsonResponse({'ok': True})
        messages.success(request, 'Marcado como no pagado.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def eliminar_gasto_pendiente(request, gasto_id):
    """Elimina el gasto pendiente Y su transacción asociada (deja de contar)."""
    gasto = get_object_or_404(GastoPendiente, id=gasto_id, usuario=request.user)
    if request.method == 'POST':
        # Borrar la transacción vinculada para que deje de contar como gasto
        if gasto.transaccion:
            gasto.transaccion.delete()
        gasto.delete()
        messages.success(request, 'Gasto pendiente eliminado.')
    return redirect('dashboard')


@login_required(login_url='/login/')
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Mis_Finanzas.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Fecha', 'Tipo', 'Categoria', 'Descripcion', 'Monto ($)'])
    for t in Transaccion.objects.filter(usuario=request.user).order_by('-fecha'):
        writer.writerow([t.fecha.strftime('%d/%m/%Y'), t.get_tipo_display(), t.categoria, t.descripcion, int(t.monto)])
    return response


@login_required(login_url='/login/')
def registrar_ingreso(request):
    return redirect('/registrar/?tipo=INGRESO')


# ===== ONBOARDING =====
from .models import UserProfile

def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(usuario=user)
    return profile


@login_required(login_url='/login/')
def onboarding(request):
    profile = get_or_create_profile(request.user)
    if profile.onboarding_completado:
        return redirect('dashboard')
    return render(request, 'finanzas/onboarding.html')


@login_required(login_url='/login/')
def completar_onboarding(request):
    if request.method == 'POST':
        ingreso_monto = request.POST.get('ingreso_monto')
        if ingreso_monto:
            try:
                Transaccion.objects.create(
                    usuario=request.user, tipo='INGRESO',
                    monto=float(ingreso_monto), categoria='Otros',
                    descripcion=request.POST.get('ingreso_desc') or 'Ingreso mensual',
                    fecha=timezone.now(),
                )
            except: pass

        deuda_acreedor = request.POST.get('deuda_acreedor')
        deuda_monto = request.POST.get('deuda_monto')
        deuda_cuotas = request.POST.get('deuda_cuotas')
        if deuda_acreedor and deuda_monto and deuda_cuotas:
            try:
                Deuda.objects.create(
                    usuario=request.user, acreedor=deuda_acreedor,
                    monto_total=float(deuda_monto), cuotas_totales=int(deuda_cuotas),
                    fecha_inicio=timezone.now().date(),
                )
            except: pass

        presupuesto_val = request.POST.get('presupuesto')
        if presupuesto_val:
            try:
                p, _ = Presupuesto.objects.get_or_create(usuario=request.user, defaults={'limite_mensual': 500000})
                p.limite_mensual = float(presupuesto_val)
                p.save()
            except: pass

        profile = get_or_create_profile(request.user)
        profile.onboarding_completado = True
        profile.save()
        messages.success(request, f'¡Bienvenido a FinApp, {request.user.username}! 🎉')
    return redirect('dashboard')


# ===== PERFIL =====
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

@login_required(login_url='/login/')
def perfil(request):
    profile = get_or_create_profile(request.user)
    from django import forms

    class PerfilForm(forms.ModelForm):
        class Meta:
            from .models import UserProfile
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

    pw_form = PasswordChangeForm(request.user)
    perfil_form = PerfilForm(instance=profile)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'perfil':
            perfil_form = PerfilForm(request.POST, instance=profile)
            if perfil_form.is_valid():
                perfil_form.save()
                nombre = request.POST.get('nombre_completo', '').strip()
                if nombre:
                    partes = nombre.split(' ', 1)
                    request.user.first_name = partes[0]
                    request.user.last_name = partes[1] if len(partes) > 1 else ''
                    request.user.save()
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('perfil')
        elif accion == 'password':
            pw_form = PasswordChangeForm(request.user, request.POST)
            if pw_form.is_valid():
                user = pw_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Contraseña actualizada.')
                return redirect('perfil')

    from .models import Transaccion, Deuda
    total_trans = Transaccion.objects.filter(usuario=request.user).count()
    total_deudas = Deuda.objects.filter(usuario=request.user).count()
    miembro_desde = request.user.date_joined.strftime('%B %Y')

    return render(request, 'finanzas/perfil.html', {
        'perfil_form': perfil_form, 'pw_form': pw_form, 'profile': profile,
        'total_trans': total_trans, 'total_deudas': total_deudas, 'miembro_desde': miembro_desde,
    })

@login_required(login_url='/login/')
def suscripciones(request):
    """Lista de suscripciones (activas e inactivas)."""
    subs = Suscripcion.objects.filter(usuario=request.user)
    activas = subs.filter(activa=True)
    total_mensual = sum(float(s.monto) for s in activas)
    return render(request, 'finanzas/suscripciones.html', {
        'suscripciones': subs,
        'total_mensual': round(total_mensual),
        'cantidad_activas': activas.count(),
    })


@login_required(login_url='/login/')
def crear_suscripcion(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        monto = request.POST.get('monto')
        dia = request.POST.get('dia_cobro', '1')
        categoria = request.POST.get('categoria', 'Suscripciones').strip() or 'Suscripciones'
        if nombre and monto:
            try:
                dia_int = max(1, min(28, int(dia)))
                Suscripcion.objects.create(
                    usuario=request.user, nombre=nombre, monto=float(monto),
                    dia_cobro=dia_int, categoria=categoria, fecha_inicio=date.today(),
                )
                # Generar el cobro del mes actual de inmediato
                generar_cobros_suscripciones(request.user)
                messages.success(request, f'Suscripción a {nombre} agregada.')
                return redirect('suscripciones')
            except (ValueError, TypeError):
                messages.warning(request, 'Revisa los datos ingresados.')
        else:
            messages.warning(request, 'Completa nombre y monto.')
    return render(request, 'finanzas/form_suscripcion.html', {})


@login_required(login_url='/login/')
def cancelar_suscripcion(request, sub_id):
    """Cancela una suscripción (deja de generar cobros). No borra el historial."""
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    if request.method == 'POST':
        if sub.activa:
            sub.activa = False
            sub.fecha_cancelada = date.today()
            sub.save()
            messages.success(request, f'{sub.nombre} cancelada. No se generarán más cobros.')
        else:
            # Reactivar
            sub.activa = True
            sub.fecha_cancelada = None
            sub.save()
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
