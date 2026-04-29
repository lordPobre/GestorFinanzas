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
from .models import Transaccion, Deuda, Presupuesto, MetaAhorro
from .forms import DeudaForm, IngresoForm, TransaccionForm, MetaAhorroForm


# --- FUNCIÓN AUXILIAR: FECHA DE CORTE ---
def get_fecha_corte(fecha_referencia=None):
    """Calcula el inicio del mes fiscal (día 5) basado en una fecha dada"""
    if not fecha_referencia:
        fecha_referencia = timezone.now().date()

    if fecha_referencia.day < 5:
        if fecha_referencia.month == 1:
            inicio = date(fecha_referencia.year - 1, 12, 5)
        else:
            inicio = date(fecha_referencia.year, fecha_referencia.month - 1, 5)
    else:
        inicio = date(fecha_referencia.year, fecha_referencia.month, 5)

    return inicio


# FIX: login_url apunta al login propio, no al admin
@login_required(login_url='/login/')
def dashboard(request):
    # 1. RECIBIR FECHA DE LA URL (Navegación entre meses)
    hoy = date.today()
    try:
        year = int(request.GET.get('year', hoy.year))
        month = int(request.GET.get('month', hoy.month))
        fecha_visualizada = date(year, month, 1)
    except ValueError:
        year = hoy.year
        month = hoy.month
        fecha_visualizada = hoy

    # 2. CALCULAR MES ANTERIOR Y SIGUIENTE
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    # 3. FECHAS DE CORTE
    referencia_fiscal = date(year, month, 15)
    fecha_inicio_corte = get_fecha_corte(referencia_fiscal)

    if fecha_inicio_corte.month == 12:
        fecha_fin_corte = date(fecha_inicio_corte.year + 1, 1, 4)
    else:
        fecha_fin_corte = date(fecha_inicio_corte.year, fecha_inicio_corte.month + 1, 4)

    # 4. TOTALES REALES
    total_ingresos = Transaccion.objects.filter(
        usuario=request.user, tipo='INGRESO',
        fecha__gte=fecha_inicio_corte, fecha__lte=fecha_fin_corte
    ).aggregate(Sum('monto'))['monto__sum'] or 0

    pagado_este_mes = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio_corte, fecha__lte=fecha_fin_corte
    ).aggregate(Sum('monto'))['monto__sum'] or 0

    # 5. LÓGICA DEL CALENDARIO Y DEUDAS DEL MES
    todas_las_deudas = Deuda.objects.filter(usuario=request.user)

    _, ultimo_dia_mes = calendar.monthrange(year, month)
    fin_mes_vis = date(year, month, ultimo_dia_mes)

    deudas_potenciales = todas_las_deudas.filter(fecha_inicio__lte=fin_mes_vis)

    cal = calendar.monthcalendar(year, month)
    eventos_mes = {}
    monto_por_pagar_mes = 0
    deudas_del_mes = []

    for d in deudas_potenciales:
        dia_vencimiento = d.fecha_inicio.day
        if dia_vencimiento > ultimo_dia_mes:
            dia_vencimiento = ultimo_dia_mes

        fecha_cobro_este_mes = date(year, month, dia_vencimiento)
        fecha_final_deuda = d.fecha_inicio + relativedelta(months=int(d.cuotas_totales) - 1)

        if d.fecha_inicio <= fecha_cobro_este_mes <= fecha_final_deuda:
            deudas_del_mes.append(d)

            if dia_vencimiento not in eventos_mes:
                eventos_mes[dia_vencimiento] = []

            # Estado de la cuota: si el mes ya paso completo = pagado, si es futuro = pendiente
            if year < hoy.year or (year == hoy.year and month < hoy.month):
                estado = 'pagado'
            elif year > hoy.year or (year == hoy.year and month > hoy.month):
                estado = 'pendiente'
            else:
                # Mes actual: verificar si ya pago esta cuota
                if d.proximo_vencimiento and d.proximo_vencimiento > fecha_cobro_este_mes:
                    estado = 'pagado'
                elif d.cuotas_pagadas >= d.cuotas_totales:
                    estado = 'pagado'
                else:
                    estado = 'pendiente'

            if estado == 'pendiente':
                monto_por_pagar_mes += float(d.monto_cuota)

            eventos_mes[dia_vencimiento].append({
                'deuda': d,
                'estado': estado,
                'monto': d.monto_cuota
            })

    # 6. CÁLCULOS DE COMPROMISOS
    # FIX: presupuesto incluye cuotas pendientes, no solo egresos manuales
    total_comprometido = round(float(pagado_este_mes) + float(monto_por_pagar_mes), 2)
    balance = round(float(total_ingresos) - total_comprometido, 2)

    # Preparar datos del calendario
    calendario_datos = []
    for semana in cal:
        semana_datos = []
        for dia in semana:
            if dia == 0:
                semana_datos.append(None)
            else:
                es_hoy = (dia == hoy.day and month == hoy.month and year == hoy.year)
                semana_datos.append({
                    'numero': dia,
                    'es_hoy': es_hoy,
                    'eventos': eventos_mes.get(dia, [])
                })
        calendario_datos.append(semana_datos)

    # 7. GRÁFICOS (REAL VS PROYECCIÓN)
    gastos_reales = Transaccion.objects.filter(tipo='EGRESO', usuario=request.user)
    data_reales = defaultdict(float)
    data_deudas = defaultdict(float)

    for g in gastos_reales:
        clave = g.fecha.strftime('%Y-%m')
        data_reales[clave] += float(g.monto)

    for d in todas_las_deudas:
        cuotas_restantes = d.cuotas_totales - d.cuotas_pagadas
        if cuotas_restantes > 0:
            inicio_pro = d.proximo_vencimiento or d.fecha_inicio
            for i in range(cuotas_restantes):
                f_cuota = inicio_pro + relativedelta(months=i)
                data_deudas[f_cuota.strftime('%Y-%m')] += float(d.monto_cuota)

    claves_ordenadas = sorted(list(set(data_reales.keys()).union(set(data_deudas.keys()))))
    meses_label = []
    montos_reales_data = []
    montos_deudas_data = []

    nombres_meses_esp = {
        '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr',
        '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Ago',
        '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'
    }

    for c in claves_ordenadas:
        anio_c, mes_c = c.split('-')
        meses_label.append(f"{nombres_meses_esp[mes_c]} {anio_c}")
        montos_reales_data.append(data_reales.get(c, 0))
        montos_deudas_data.append(data_deudas.get(c, 0))

    # Deuda total GLOBAL
    deudas_activas_global = todas_las_deudas.filter(cuotas_pagadas__lt=F('cuotas_totales'))
    deuda_total_restante = sum(float(d.monto_restante) for d in deudas_activas_global)

    # 9. DONA Y ÚLTIMOS MOVIMIENTOS
    gastos_del_mes = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio_corte, fecha__lte=fecha_fin_corte
    )
    agrupado_categorias = gastos_del_mes.values('categoria').annotate(total=Sum('monto')).order_by('-total')

    ultimas_transacciones = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]

    # 11. PRESUPUESTO
    # FIX: el porcentaje de presupuesto incluye cuotas pendientes del mes
    presupuesto, _ = Presupuesto.objects.get_or_create(usuario=request.user, defaults={'limite_mensual': 500000})
    limite_presupuesto = float(presupuesto.limite_mensual)
    gasto_real_total = float(pagado_este_mes) + float(monto_por_pagar_mes)
    porcentaje_presupuesto = min((gasto_real_total / limite_presupuesto * 100), 100) if limite_presupuesto > 0 else 0
    color_presupuesto = 'bg-green-500' if porcentaje_presupuesto < 60 else 'bg-yellow-400' if porcentaje_presupuesto < 90 else 'bg-red-500'

    metas = MetaAhorro.objects.filter(usuario=request.user)

    # 12. CONTEXTO
    context = {
        'total_ingresos': round(float(total_ingresos), 2),
        'pagado_este_mes': round(float(pagado_este_mes), 2),
        'por_pagar': round(float(monto_por_pagar_mes), 2),
        'total_comprometido': total_comprometido,
        'balance': balance,
        'deuda_total_restante': round(deuda_total_restante, 2),
        'deudas': deudas_del_mes,
        'fecha_corte': fecha_inicio_corte,
        'calendario': calendario_datos,
        'nombre_mes': fecha_visualizada.strftime('%B %Y').capitalize(),
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
        'meses_json': json.dumps(meses_label),
        'montos_reales_json': json.dumps(montos_reales_data),
        'montos_deudas_json': json.dumps(montos_deudas_data),
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'ultimas_transacciones': ultimas_transacciones,
        'categorias_pie_json': json.dumps([item['categoria'] or 'Otros' for item in agrupado_categorias]),
        'datos_pie_json': json.dumps([float(item['total']) for item in agrupado_categorias]),
        'limite_presupuesto': limite_presupuesto,
        'porcentaje_presupuesto': round(porcentaje_presupuesto, 1),
        'color_presupuesto': color_presupuesto,
        'metas': metas,
        'year': year,
        'month': month,
    }

    return render(request, 'finanzas/dashboard.html', context)


@login_required(login_url='/login/')
def pagar_cuota(request, deuda_id):
    if request.method == 'POST':
        deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)

        if deuda.cuotas_pagadas < deuda.cuotas_totales:
            deuda.cuotas_pagadas += 1
            deuda.save()

            # FIX: se registra la categoria de la deuda en la transaccion automatica
            Transaccion.objects.create(
                usuario=request.user,
                tipo='EGRESO',
                monto=deuda.monto_cuota,
                categoria=deuda.categoria,
                descripcion=f'Cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} - {deuda.acreedor}',
                fecha=timezone.now(),
            )
            messages.success(request, f"Pago de {deuda.acreedor} registrado correctamente.")
        else:
            messages.warning(request, f"{deuda.acreedor} ya tiene todas sus cuotas pagadas.")

    return redirect('dashboard')


@login_required(login_url='/login/')
def crear_deuda(request):
    if request.method == 'POST':
        form = DeudaForm(request.POST)
        if form.is_valid():
            deuda = form.save(commit=False)
            deuda.usuario = request.user
            deuda.save()
            messages.success(request, f"Deuda '{deuda.acreedor}' creada correctamente.")
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
            messages.success(request, "Deuda actualizada correctamente.")
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
    """Vista unificada para registrar ingresos Y egresos manuales"""
    tipo_inicial = request.GET.get('tipo', 'INGRESO')
    if request.method == 'POST':
        form = TransaccionForm(request.POST)
        if form.is_valid():
            t = form.save(commit=False)
            t.usuario = request.user
            t.save()
            tipo_label = "Ingreso" if t.tipo == 'INGRESO' else "Gasto"
            messages.success(request, f"{tipo_label} registrado correctamente.")
            return redirect('dashboard')
    else:
        form = TransaccionForm(initial={'tipo': tipo_inicial})

    return render(request, 'finanzas/form_transaccion.html', {'form': form, 'tipo_inicial': tipo_inicial})


# Compatibilidad con URL anterior
@login_required(login_url='/login/')
def registrar_ingreso(request):
    return redirect(f'/registrar/?tipo=INGRESO')


@login_required(login_url='/login/')
def editar_transaccion(request, transaccion_id):
    transaccion = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=transaccion)
        if form.is_valid():
            form.save()
            messages.success(request, "Movimiento actualizado.")
            return redirect('dashboard')
    else:
        form = TransaccionForm(instance=transaccion)

    return render(request, 'finanzas/form_transaccion.html', {'form': form, 'editar': True})


@login_required(login_url='/login/')
def eliminar_transaccion(request, transaccion_id):
    transaccion = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        transaccion.delete()
        messages.success(request, "Movimiento eliminado.")
    return redirect('dashboard')


@login_required(login_url='/login/')
def estadisticas(request):
    deudas = Deuda.objects.filter(usuario=request.user)

    labels = []
    data_cuota = []
    data_restante = []

    for deuda in deudas:
        if deuda.cuotas_pagadas < deuda.cuotas_totales:
            labels.append(deuda.acreedor)
            data_cuota.append(float(deuda.monto_cuota))
            # FIX: también mostramos monto_restante en estadisticas
            data_restante.append(float(deuda.monto_restante))

    context = {
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data_cuota),
        'data_restante_json': json.dumps(data_restante),
    }

    return render(request, 'finanzas/estadisticas.html', context)


def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Bienvenido, {user.username}!")
            return redirect('dashboard')
    else:
        form = UserCreationForm()

    return render(request, 'registration/registro.html', {'form': form})


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
            messages.success(request, "Meta actualizada.")
            return redirect('dashboard')
    else:
        form = MetaAhorroForm(instance=meta)

    return render(request, 'finanzas/crear_meta.html', {'form': form, 'editar': True, 'meta': meta})


@login_required(login_url='/login/')
def eliminar_meta(request, meta_id):
    meta = get_object_or_404(MetaAhorro, id=meta_id, usuario=request.user)
    if request.method == 'POST':
        meta.delete()
        messages.success(request, "Meta eliminada.")
    return redirect('dashboard')


@login_required(login_url='/login/')
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Mis_Finanzas.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Fecha', 'Tipo', 'Categoria', 'Descripcion', 'Monto ($)'])

    transacciones = Transaccion.objects.filter(usuario=request.user).order_by('-fecha')
    for t in transacciones:
        writer.writerow([
            t.fecha.strftime('%d/%m/%Y'),
            t.tipo,
            t.categoria,
            t.descripcion,
            round(float(t.monto), 0)
        ])

    return response
