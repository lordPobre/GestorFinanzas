import csv
import calendar
import json
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
from .models import Transaccion, Deuda, Presupuesto, MetaAhorro
from .forms import DeudaForm, IngresoForm, MetaAhorroForm
from django.http import HttpResponse


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

    # 3. FECHAS DE CORTE
    referencia_fiscal = date(year, month, 15) 
    fecha_inicio = get_fecha_corte(referencia_fiscal)
    
    if fecha_inicio.month == 12:
        fecha_fin = date(fecha_inicio.year + 1, 1, 4)
    else:
        fecha_fin = date(fecha_inicio.year, fecha_inicio.month + 1, 4)

    # 4. TOTALES REALES (Lo que ya ingresó/salió del banco)
    total_ingresos = Transaccion.objects.filter(
        usuario=request.user, tipo='INGRESO', # Asegúrate que el tipo sea 'INGRESO' en tu BD
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(Sum('monto'))['monto__sum'] or 0 

    pagado_este_mes = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO', # Asegúrate que el tipo sea 'EGRESO' en tu BD
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    ).aggregate(Sum('monto'))['monto__sum'] or 0

    # 5. LÓGICA DEL CALENDARIO Y DEUDA PENDIENTE
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

            # Estado de la cuota en el mes actual
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

            # Si está pendiente en ESTE mes, lo sumamos a lo que falta por pagar
            if estado == 'pendiente':
                monto_por_pagar_mes += float(d.monto_cuota)

            eventos_mes[dia_vencimiento].append({
                'deuda': d,
                'estado': estado,
                'monto': d.monto_cuota
            })

    # 6. CÁLCULOS DE COMPROMISOS (NUEVA LÓGICA)
    total_comprometido = int(pagado_este_mes) + int(monto_por_pagar_mes)
    balance = int(total_ingresos) - total_comprometido

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

   # 7. GRÁFICOS COMBINADOS (APILADOS: REAL VS PROYECCIÓN)
    # =====================================================================
    gastos_reales = Transaccion.objects.filter(tipo='EGRESO', usuario=request.user)
    
    # Creamos dos diccionarios separados
    data_reales = defaultdict(float)
    data_deudas = defaultdict(float)

    # A. Sumamos los gastos reales (Histórico y presente)
    for g in gastos_reales:
        clave = g.fecha.strftime('%Y-%m')
        data_reales[clave] += float(g.monto)

    # B. Sumamos la proyección de deudas (Futuro)
    for d in deudas:
        cuotas_restantes = d.cuotas_totales - d.cuotas_pagadas
        if cuotas_restantes > 0:
            inicio_proyeccion = d.proximo_vencimiento or d.fecha_inicio
            for i in range(cuotas_restantes):
                fecha_cuota = inicio_proyeccion + relativedelta(months=i)
                clave = fecha_cuota.strftime('%Y-%m')
                data_deudas[clave] += float(d.monto_cuota)

    # C. Unimos y ordenamos todos los meses que existan en ambos lados
    todas_las_claves = set(data_reales.keys()).union(set(data_deudas.keys()))
    claves_ordenadas = sorted(list(todas_las_claves))

    meses_label = []
    montos_reales_data = []
    montos_deudas_data = []
    
    nombres_meses_esp = {
        '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
        '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic'
    }

    for clave in claves_ordenadas:
        anio, mes_num = clave.split('-')
        nombre_bonito = f"{nombres_meses_esp[mes_num]} {anio}"
        meses_label.append(nombre_bonito)
        # Si no hay gastos en un mes, agrega 0 para que no falle el gráfico
        montos_reales_data.append(data_reales.get(clave, 0))
        montos_deudas_data.append(data_deudas.get(clave, 0))

    nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

    # Sumamos el monto restante de todas tus deudas activas
    deuda_total_restante = sum(float(d.monto_restante) for d in deudas)

    # NUEVO: 9. DATOS PARA GRÁFICO DE DONA (CATEGORÍAS)
    # =====================================================================
    # Usamos los gastos del mes actual (pagado_este_mes)
    gastos_del_mes = Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin
    )
    
    # Agrupamos por categoría y sumamos
    agrupado_categorias = gastos_del_mes.values('categoria').annotate(total=Sum('monto')).order_by('-total')
    
    categorias_label = [item['categoria'] or 'Otros' for item in agrupado_categorias]
    categorias_data = [float(item['total']) for item in agrupado_categorias]

    # =====================================================================
    # NUEVO: 10. ÚLTIMOS MOVIMIENTOS
    # =====================================================================
    # Traemos las últimas 5 transacciones (sin importar si es ingreso o egreso)
    ultimas_transacciones = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:5]

    # =====================================================================
    # NUEVO: 11. GAMIFICACIÓN (PRESUPUESTO Y ALCANCÍAS)
    # =====================================================================
    
    # 1. Lógica del Presupuesto
    presupuesto, created = Presupuesto.objects.get_or_create(usuario=request.user, defaults={'limite_mensual': 500000})
    limite_presupuesto = float(presupuesto.limite_mensual)
    gastado = float(pagado_este_mes) # Usa la variable que ya tienes calculada de egresos
    
    porcentaje_presupuesto = (gastado / limite_presupuesto * 100) if limite_presupuesto > 0 else 0
    porcentaje_presupuesto = min(porcentaje_presupuesto, 100) # Para que la barra no se salga del contenedor

    # Sistema de semáforo para el color
    if porcentaje_presupuesto < 60:
        color_presupuesto = 'bg-green-500'     # Vas súper bien
    elif porcentaje_presupuesto < 90:
        color_presupuesto = 'bg-yellow-400'    # Cuidado
    else:
        color_presupuesto = 'bg-red-500'       # ¡Alerta roja!

    # 2. Lógica de las Alcancías
    metas = MetaAhorro.objects.filter(usuario=request.user)

    # 8. CONTEXTO A ENVIAR AL TEMPLATE
    context = {
        'total_ingresos': total_ingresos,
        'pagado_este_mes': int(pagado_este_mes),           
        'por_pagar': int(monto_por_pagar_mes),             
        'total_comprometido': total_comprometido,          
        'deuda_total_restante': int(deuda_total_restante),
        'balance': balance,
        'deudas': deudas,
        'fecha_corte': fecha_inicio,
        'calendario': calendario_datos,
        'nombre_mes': fecha_visualizada.strftime('%B %Y').capitalize(),
        'dias_semana': nombres_dias,
        
        # --- AQUÍ CAMBIAMOS LAS VARIABLES DEL JSON ---
        'meses_json': json.dumps(meses_label),
        'montos_reales_json': json.dumps(montos_reales_data), 
        'montos_deudas_json': json.dumps(montos_deudas_data),
        # ---------------------------------------------
        
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,

        'ultimas_transacciones': ultimas_transacciones,
        'categorias_pie_json': json.dumps(categorias_label),
        'datos_pie_json': json.dumps(categorias_data),

        'limite_presupuesto': limite_presupuesto,
        'porcentaje_presupuesto': porcentaje_presupuesto,
        'color_presupuesto': color_presupuesto,
        'metas': metas,
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

@login_required(login_url='/admin/login/')
def crear_meta(request):
    if request.method == 'POST':
        form = MetaAhorroForm(request.POST)
        if form.is_valid():
            meta = form.save(commit=False)
            meta.usuario = request.user # Le asignamos la meta al usuario actual
            meta.save()
            return redirect('dashboard')
    else:
        form = MetaAhorroForm()
        
    return render(request, 'finanzas/crear_meta.html', {'form': form})

@login_required(login_url='/admin/login/')
def exportar_excel(request):
    # Configuramos la respuesta para descargar un archivo con soporte para acentos (utf-8-sig)
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="Mis_Finanzas.csv"'

    # Usamos punto y coma porque el Excel en español lo lee mejor
    writer = csv.writer(response, delimiter=';') 
    
    # Escribimos los encabezados de las columnas
    writer.writerow(['Fecha', 'Tipo', 'Categoría', 'Descripción', 'Monto ($)'])

    # Traemos las transacciones
    transacciones = Transaccion.objects.filter(usuario=request.user).order_by('-fecha')
    
    for t in transacciones:
        writer.writerow([t.fecha.strftime('%d/%m/%Y'), t.tipo, t.categoria, t.descripcion, int(t.monto)])

    return response