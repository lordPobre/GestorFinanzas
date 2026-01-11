from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from django.utils import timezone
from datetime import date
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
import calendar
import json
from .models import Transaccion, Deuda
from .forms import DeudaForm, IngresoForm

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

@login_required
@login_required(login_url='/admin/login/')
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

    # 3. TOTALES REALES (Lo que ya salió del banco)
    referencia_fiscal = date(year, month, 15) 
    fecha_inicio = get_fecha_corte(referencia_fiscal)
    
    if fecha_inicio.month == 12:
        fecha_fin = date(fecha_inicio.year + 1, 1, 4)
    else:
        fecha_fin = date(fecha_inicio.year, fecha_inicio.month + 1, 4)

    total_ingresos = Transaccion.objects.filter(
        usuario=request.user, tipo='INGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(Sum('monto'))['monto__sum'] or 0 

    total_egresos_reales = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(Sum('monto'))['monto__sum'] or 0

    # 4. LÓGICA DEL CALENDARIO Y DEUDA PENDIENTE
    deudas = Deuda.objects.filter(usuario=request.user)
    _, num_days = calendar.monthrange(year, month)
    cal = calendar.monthcalendar(year, month)
    eventos_mes = {}
    
    monto_por_pagar_mes = 0 

    for d in deudas:
        dia_vencimiento = d.fecha_inicio.day
        if dia_vencimiento > num_days: dia_vencimiento = num_days
        
        fecha_cobro_este_mes = date(year, month, dia_vencimiento)
        
        if d.fecha_inicio <= fecha_cobro_este_mes <= d.fecha_fin_estimada:
            
            if dia_vencimiento not in eventos_mes:
                eventos_mes[dia_vencimiento] = []

            # Estado
            if fecha_cobro_este_mes < hoy and (year < hoy.year or (year == hoy.year and month < hoy.month)):
                 estado = 'pagado'
            elif fecha_cobro_este_mes > hoy:
                 estado = 'pendiente'
            else:
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

    # 5. CÁLCULO FINAL DE PROYECCIÓN
    total_egresos_proyectado = int(total_egresos_reales) + int(monto_por_pagar_mes)
    balance = int(total_ingresos) - total_egresos_proyectado

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

    # =========================================================================
    # 6. GRÁFICOS COMBINADOS (REAL + PROYECCIÓN DE DEUDAS) <-- AQUÍ CAMBIAMOS
    # =========================================================================
    
    # A. Obtenemos Gastos Reales Históricos
    gastos_reales = Transaccion.objects.filter(tipo='EGRESO', usuario=request.user)
    
    # Usamos un diccionario para sumar por mes: {'2024-01': 50000, ...}
    data_grafico = defaultdict(float)

    for g in gastos_reales:
        clave = g.fecha.strftime('%Y-%m') # Agrupamos por Año-Mes
        data_grafico[clave] += float(g.monto)

    # B. Sumamos las Deudas Pendientes (Proyección a Futuro)
    for d in deudas:
        # Calculamos cuántas cuotas le faltan
        cuotas_restantes = d.cuotas_totales - d.cuotas_pagadas
        
        if cuotas_restantes > 0:
            # Empezamos a proyectar desde el próximo vencimiento
            inicio_proyeccion = d.proximo_vencimiento or d.fecha_inicio
            
            # Sumamos el valor de la cuota a los meses futuros en el gráfico
            for i in range(cuotas_restantes):
                fecha_cuota = inicio_proyeccion + relativedelta(months=i)
                clave = fecha_cuota.strftime('%Y-%m')
                data_grafico[clave] += float(d.monto_cuota)

    # C. Preparamos los datos para Chart.js
    # Ordenamos cronológicamente
    claves_ordenadas = sorted(data_grafico.keys())
    
    meses_label = []
    montos_data = []
    
    # Diccionario para traducir mes a español
    nombres_meses_esp = {
        '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
        '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'
    }

    for clave in claves_ordenadas:
        anio, mes_num = clave.split('-')
        # Creamos la etiqueta, ej: "Ene 2024"
        nombre_bonito = f"{nombres_meses_esp[mes_num]} {anio}"
        
        meses_label.append(nombre_bonito)
        montos_data.append(data_grafico[clave])

    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    # =========================================================================

    context = {
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos_proyectado,
        'por_pagar': int(monto_por_pagar_mes),
        'balance': balance,
        'deudas': deudas,
        'fecha_corte': fecha_inicio,
        'calendario': calendario_datos,
        'nombre_mes': fecha_visualizada.strftime('%B %Y').capitalize(),
        'dias_semana': nombres_dias,
        'meses_json': json.dumps(meses_label),
        'montos_json': json.dumps(montos_data),      
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
    }
    
    return render(request, 'finanzas/dashboard.html', context)


@login_required
def pagar_cuota(request, deuda_id):
    if request.method == 'POST':
        deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
        
        if deuda.cuotas_pagadas < deuda.cuotas_totales:
            # 1. Actualizar Deuda
            deuda.cuotas_pagadas += 1
            deuda.monto_pagado += deuda.monto_cuota
            deuda.save()
            
            # 2. Crear Gasto Automáticamente
            Transaccion.objects.create(
                usuario=request.user,
                tipo='EGRESO',
                monto=deuda.monto_cuota,
                descripcion=f'Pago cuota {deuda.cuotas_pagadas}/{deuda.cuotas_totales} - {deuda.acreedor}',
                fecha=timezone.now(),
            )
            messages.success(request, f"¡Pago de {deuda.acreedor} registrado!")
            
    return redirect('dashboard')

@login_required(login_url='/admin/login/')
def crear_deuda(request):
    if request.method == 'POST':
        form = DeudaForm(request.POST)
        if form.is_valid():
            deuda = form.save(commit=False)
            deuda.usuario = request.user
            deuda.save()
            return redirect('dashboard')
        else:
            print("ERRORES DEL FORMULARIO:", form.errors) 
    else:
        form = DeudaForm()
    
    return render(request, 'finanzas/form_deuda.html', {'form': form})

@login_required(login_url='/admin/login/')
def eliminar_deuda(request, deuda_id):
    deuda = get_object_or_404(Deuda, id=deuda_id, usuario=request.user)
    deuda.delete()
    return redirect('dashboard')

@login_required(login_url='/admin/login/')
def registrar_ingreso(request):
    if request.method == 'POST':
        form = IngresoForm(request.POST)
        if form.is_valid():
            ingreso = form.save(commit=False)
            ingreso.usuario = request.user
            ingreso.tipo = 'INGRESO'
            ingreso.save()
            return redirect('dashboard')
    else:
        form = IngresoForm()
    
    return render(request, 'finanzas/form_ingreso.html', {'form': form})

@login_required(login_url='/admin/login/')
def estadisticas(request):
    # 1. Obtener deudas activas del usuario
    deudas = Deuda.objects.filter(usuario=request.user)
    
    labels = []
    data = []
    colores = []
    
    # 2. Extraer datos solo de las deudas que faltan por pagar
    for deuda in deudas:
        if deuda.cuotas_pagadas < deuda.cuotas_totales:
            labels.append(deuda.acreedor)
            # Usamos la propiedad .monto_cuota que creamos antes
            data.append(float(deuda.monto_cuota)) 
            
    # 3. Contexto
    context = {
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data),
    }
    
    return render(request, 'finanzas/estadisticas.html', context)

def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Logueamos al usuario automáticamente tras registrarse
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'registration/registro.html', {'form': form})