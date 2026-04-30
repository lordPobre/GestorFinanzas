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
from .forms import DeudaForm, TransaccionForm, MetaAhorroForm


@login_required(login_url='/login/')
def dashboard(request):
    hoy = date.today()

    # Navegación entre meses
    try:
        year = int(request.GET.get('year', hoy.year))
        month = int(request.GET.get('month', hoy.month))
        date(year, month, 1)  # valida que sea fecha real
    except ValueError:
        year, month = hoy.year, hoy.month

    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    # Rango del mes calendario simple (sin fecha de corte confusa)
    _, ultimo_dia = calendar.monthrange(year, month)
    fecha_inicio = date(year, month, 1)
    fecha_fin = date(year, month, ultimo_dia)
    nombre_mes = date(year, month, 1).strftime('%B %Y').capitalize()

    # --- INGRESOS del mes ---
    total_ingresos = Transaccion.objects.filter(
        usuario=request.user, tipo='INGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(total=Sum('monto'))['total'] or 0

    # --- GASTOS del mes (supermercado, bencina, etc) ---
    total_gastos = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(total=Sum('monto'))['total'] or 0

    # --- CUOTAS DE DEUDAS del mes ---
    todas_las_deudas = Deuda.objects.filter(usuario=request.user)
    deudas_del_mes = []
    cuotas_pagadas_mes = 0.0
    cuotas_pendientes_mes = 0.0
    eventos_mes = {}

    for d in todas_las_deudas:
        dia_venc = d.fecha_inicio.day
        if dia_venc > ultimo_dia:
            dia_venc = ultimo_dia
        fecha_cobro = date(year, month, dia_venc)
        fecha_fin_deuda = d.fecha_inicio + relativedelta(months=int(d.cuotas_totales) - 1)

        if not (d.fecha_inicio <= fecha_cobro <= fecha_fin_deuda):
            continue

        deudas_del_mes.append(d)

        # Estado de la cuota
        if year < hoy.year or (year == hoy.year and month < hoy.month):
            estado = 'pagado'
        elif year > hoy.year or (year == hoy.year and month > hoy.month):
            estado = 'pendiente'
        else:
            if d.proximo_vencimiento and d.proximo_vencimiento > fecha_cobro:
                estado = 'pagado'
            elif d.cuotas_pagadas >= d.cuotas_totales:
                estado = 'pagado'
            else:
                estado = 'pendiente'

        monto_cuota = float(d.monto_cuota)
        if estado == 'pagado':
            cuotas_pagadas_mes += monto_cuota
        else:
            cuotas_pendientes_mes += monto_cuota

        if dia_venc not in eventos_mes:
            eventos_mes[dia_venc] = []
        eventos_mes[dia_venc].append({'deuda': d, 'estado': estado, 'monto': d.monto_cuota})

    total_cuotas_mes = cuotas_pagadas_mes + cuotas_pendientes_mes

    # --- RESUMEN CLARO ---
    # Lo que ya salió: gastos + cuotas pagadas
    ya_gaste = float(total_gastos) + cuotas_pagadas_mes
    # Lo que falta pagar este mes: cuotas pendientes
    por_pagar = cuotas_pendientes_mes
    # Lo que me queda libre = ingresos - todo lo comprometido
    disponible = float(total_ingresos) - ya_gaste - por_pagar

    # --- CALENDARIO ---
    cal = calendar.monthcalendar(year, month)
    calendario_datos = []
    for semana in cal:
        semana_datos = []
        for dia in semana:
            if dia == 0:
                semana_datos.append(None)
            else:
                semana_datos.append({
                    'numero': dia,
                    'es_hoy': (dia == hoy.day and month == hoy.month and year == hoy.year),
                    'eventos': eventos_mes.get(dia, [])
                })
        calendario_datos.append(semana_datos)

    # --- GRÁFICO: últimos 6 meses, barras apiladas claras ---
    meses_labels = []
    datos_ingresos = []
    datos_gastos = []
    datos_cuotas = []
    nombres_meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        _, ult = calendar.monthrange(f.year, f.month)
        fi = date(f.year, f.month, 1)
        ff = date(f.year, f.month, ult)

        ing = float(Transaccion.objects.filter(
            usuario=request.user, tipo='INGRESO', fecha__gte=fi, fecha__lte=ff
        ).aggregate(t=Sum('monto'))['t'] or 0)

        gas = float(Transaccion.objects.filter(
            usuario=request.user, tipo='EGRESO', fecha__gte=fi, fecha__lte=ff
        ).aggregate(t=Sum('monto'))['t'] or 0)

        # Cuotas de deudas en ese mes
        cuotas_m = 0.0
        for d in todas_las_deudas:
            dv = d.fecha_inicio.day
            if dv > ult: dv = ult
            fc = date(f.year, f.month, dv)
            ffd = d.fecha_inicio + relativedelta(months=int(d.cuotas_totales) - 1)
            if d.fecha_inicio <= fc <= ffd:
                cuotas_m += float(d.monto_cuota)

        meses_labels.append(f"{nombres_meses[f.month-1]} {f.year}")
        datos_ingresos.append(ing)
        datos_gastos.append(gas)
        datos_cuotas.append(cuotas_m)

    # --- DONA DE GASTOS por categoría ---
    gastos_categoria = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).values('categoria').annotate(total=Sum('monto')).order_by('-total')

    # --- ÚLTIMAS TRANSACCIONES ---
    ultimas = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]

    # --- DEUDA TOTAL GLOBAL ---
    deuda_total = sum(float(d.monto_restante) for d in todas_las_deudas.filter(cuotas_pagadas__lt=F('cuotas_totales')))

    # --- METAS ---
    metas = MetaAhorro.objects.filter(usuario=request.user)

    context = {
        # Navegación
        'nombre_mes': nombre_mes,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],

        # Números principales
        'total_ingresos': round(float(total_ingresos), 0),
        'total_gastos': round(float(total_gastos), 0),
        'total_cuotas_mes': round(total_cuotas_mes, 0),
        'cuotas_pagadas_mes': round(cuotas_pagadas_mes, 0),
        'cuotas_pendientes_mes': round(cuotas_pendientes_mes, 0),
        'ya_gaste': round(ya_gaste, 0),
        'por_pagar': round(por_pagar, 0),
        'disponible': round(disponible, 0),
        'deuda_total': round(deuda_total, 0),

        # Listas
        'deudas': deudas_del_mes,
        'ultimas': ultimas,
        'metas': metas,
        'calendario': calendario_datos,

        # Gráficos
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
    if request.method == 'POST':
        deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
        if deuda.cuotas_pagadas < deuda.cuotas_totales:
            deuda.cuotas_pagadas += 1
            deuda.save()
            Transaccion.objects.create(
                usuario=request.user,
                tipo='EGRESO',
                monto=deuda.monto_cuota,
                categoria=deuda.categoria,
                descripcion=f'Cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} — {deuda.acreedor}',
                fecha=timezone.now(),
            )
            messages.success(request, f'Cuota de {deuda.acreedor} registrada.')
        else:
            messages.warning(request, f'{deuda.acreedor} ya está pagada completamente.')
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
            label = 'Ingreso' if t.tipo == 'INGRESO' else 'Gasto'
            messages.success(request, f'{label} registrado.')
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
    return render(request, 'finanzas/form_transaccion.html', {'form': form, 'editar': True})


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
            messages.success(request, f'Bienvenido, {user.username}!')
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
def exportar_excel(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Mis_Finanzas.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Fecha', 'Tipo', 'Categoria', 'Descripcion', 'Monto ($)'])
    for t in Transaccion.objects.filter(usuario=request.user).order_by('-fecha'):
        writer.writerow([t.fecha.strftime('%d/%m/%Y'), t.get_tipo_display(), t.categoria, t.descripcion, int(t.monto)])
    return response


# Compatibilidad con URL antigua
@login_required(login_url='/login/')
def registrar_ingreso(request):
    return redirect('/registrar/?tipo=INGRESO')
