"""Las pantallas de plata: panel, cuotas, movimientos, metas, préstamos.

Lo de la cuenta —entrar, registro, perfil, datos personales, borrado— vive
en views_cuenta.py. Este módulo no lo importa; es al revés, así que las dos
mitades se pueden leer y probar por separado.
"""
import calendar
import csv
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from dateutil.relativedelta import relativedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, F, Sum
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control

from .forms import DeudaForm, MetaAhorroForm, TransaccionForm
from . import exportar
from .seguridad import limitar
from .models import (AbonoPrestamo, AporteMeta, Categoria, Deuda, GastoPendiente,
                     MetaAhorro, PagoCuota, PagoServicio, Persona, Prestamo,
                     Presupuesto, Suscripcion, Transaccion, UserProfile)

NOMBRES_MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
MESES_LARGOS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

logger = logging.getLogger('finanzas')

def nombre_mes_es(year, month, capitalizado=True):
    """Mes en español.

    strftime('%B') usa el locale del SISTEMA, no LANGUAGE_CODE de Django, así
    que en el servidor devolvía 'August' aunque la app esté en español.
    """
    texto = f'{MESES_LARGOS[month - 1]} {year}'
    return texto.capitalize() if capitalizado else texto

def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(usuario=user)
    return profile

def _redirigir(request, por_defecto='dashboard'):
    """Vuelve a la pantalla desde la que se hizo la acción.

    El campo 'next' llega en tres formas y hay que distinguirlas, porque
    redirect() interpreta como NOMBRE DE VISTA cualquier cadena que no
    empiece por '/' o 'http':

      '/cuotas/'                  → una ruta: se usa tal cual
      '?year=2026&month=8'        → solo la consulta: hay que pegarle la ruta
                                     actual, o redirect() la toma por nombre
                                     de vista y revienta con NoReverseMatch
      'deudas'                    → un nombre de ruta

    Además se rechaza cualquier destino externo ('//otro.com' o
    'http://…'): un 'next' que sale del sitio es una redirección abierta.
    """
    destino = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if not destino:
        return redirect(por_defecto)

    if destino.startswith('?'):
        base = request.POST.get('next_path') or request.path
        if base == request.path:
            base = reverse(por_defecto)
        return redirect(f'{base}{destino}')

    if destino.startswith('/') and not destino.startswith('//'):
        return redirect(destino)

    if '/' not in destino and ':' not in destino:
        try:
            return redirect(destino)
        except NoReverseMatch:
            pass

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

    qs_gastos = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin, es_cuota=False,
    )
    gastos = float(qs_gastos.aggregate(t=Sum('monto'))['t'] or 0)

    gastos_pagados = float(qs_gastos.filter(pagado=True)
                                    .aggregate(t=Sum('monto'))['t'] or 0)
    gastos_por_pagar = gastos - gastos_pagados

    periodo = year * 100 + month

    deudas = Deuda.objects.filter(usuario=usuario).prefetch_related('pagos')
    cuotas_pagadas = 0.0
    cuotas_pendientes = 0.0
    eventos = {}

    for d in deudas:
        if periodo not in d.periodos_programados:
            continue

        fecha_cobro = d.fecha_cobro_de(periodo)
        dia_venc = fecha_cobro.day

        pago = next((p for p in d.pagos.all() if p.periodo == periodo), None)
        estado = 'pagado' if pago else 'pendiente'

        monto_cuota = pago.monto if pago else d.monto_cuota_de(periodo)
        monto = float(monto_cuota)

        if estado == 'pagado':
            cuotas_pagadas += monto
        else:
            cuotas_pendientes += monto

        eventos.setdefault(dia_venc, []).append({
            'deuda': d, 'estado': estado, 'monto': monto_cuota,
            'periodo': periodo, 'pago': pago,
            'atrasado': estado == 'pendiente' and fecha_cobro < hoy,
        })

    total_cuotas = cuotas_pagadas + cuotas_pendientes

    servicios_pagados = 0.0
    servicios_pendientes = 0.0
    for s in Suscripcion.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if periodo not in s.periodos_programados:
            continue
        monto = float(s.monto)
        if s.esta_pagada_en(periodo):
            servicios_pagados += monto
        else:
            servicios_pendientes += monto

    atrasado_arrastrado = 0.0
    cuotas_arrastradas = []
    if (year, month) == (hoy.year, hoy.month):
        for d in deudas:
            for p in d.periodos_atrasados:
                if p >= periodo:
                    continue
                monto_p = float(d.monto_cuota_de(p))
                atrasado_arrastrado += monto_p
                cuotas_arrastradas.append({
                    'deuda': d,
                    'periodo': p,
                    'monto': monto_p,
                    'etiqueta': nombre_mes_es(p // 100, p % 100),
                })
    cuotas_arrastradas.sort(key=lambda c: c['periodo'])

    comprometido = gastos + total_cuotas + atrasado_arrastrado
    disponible = ingresos - comprometido

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
        'gastos_pagados': gastos_pagados,
        'gastos_por_pagar': gastos_por_pagar,
        'cuotas_pagadas_mes': cuotas_pagadas,
        'cuotas_pendientes_mes': cuotas_pendientes,
        'total_cuotas_mes': total_cuotas,
        'servicios_pagados_mes': servicios_pagados,
        'servicios_pendientes_mes': servicios_pendientes,
        'total_servicios_mes': servicios_pagados + servicios_pendientes,
        'atrasado_arrastrado': atrasado_arrastrado,
        'cuotas_arrastradas': cuotas_arrastradas,
        'comprometido': comprometido,
        'disponible': disponible,
        'dias_restantes': dias_restantes,
        'por_dia': max(0.0, disponible) / dias_restantes,
        'pct_gastado': round(min(100, gastos / base * 100)),
        'pct_por_pagar': round(min(100, cuotas_pendientes / base * 100)),
        'pct_disponible': round(min(100, max(0.0, disponible) / base * 100)),
        'eventos': eventos,
    }

def salud_financiera(usuario, resumen_actual=None):
    """Puntaje 0-100 del mes en curso, para el bloque del sidebar.

    Tres cosas, con el peso que tienen en la vida real:
    que no gastes más de lo que entra, que las cuotas no te ahoguen,
    y que quede algo libre. Nada de esto necesita IA.

    Si quien llama ya calculó el resumen del mes en curso (el dashboard lo
    hace siempre), se puede pasar en 'resumen_actual' para no repetir las
    mismas consultas.
    """
    hoy = date.today()
    r = resumen_actual if resumen_actual is not None else resumen_mes(usuario, hoy.year, hoy.month)
    if r['ingresos'] <= 0:
        return {'salud_score': None, 'salud_label': '', 'salud_nota': ''}

    ingresos = r['ingresos']
    dti = r['total_cuotas_mes'] / ingresos * 100
    margen = r['disponible'] / ingresos * 100

    score = 100
    if r['disponible'] < 0:
        score -= 45
    elif margen < 10:
        score -= 20
    elif margen < 20:
        score -= 8

    if dti > 45:
        score -= 30
    elif dti > 35:
        score -= 18
    elif dti > 20:
        score -= 8

    gasto_pct = r['gastos'] / ingresos * 100
    if gasto_pct > 80:
        score -= 15
    elif gasto_pct > 65:
        score -= 6

    score = max(0, min(100, round(score)))

    if score >= 80:
        label = 'muy buena'
    elif score >= 60:
        label = 'buena'
    elif score >= 40:
        label = 'justa'
    else:
        label = 'apretada'

    if r['disponible'] < 0:
        nota = 'Este mes gastas más de lo que entra.'
    elif dti > 35:
        nota = f'El {round(dti)}% de lo que entra se va en cuotas.'
    elif margen < 10:
        nota = 'Te queda muy poco libre para imprevistos.'
    elif gasto_pct > 65:
        nota = f'Llevas gastado el {round(gasto_pct)}% de lo que entró.'
    else:
        nota = 'Gastas menos de lo que entra y las cuotas están bajo control.'

    return {'salud_score': score, 'salud_label': label, 'salud_nota': nota}

def serie_cuotas(usuario, atras=6, adelante=6):
    """Cuotas mes a mes, incluyendo los meses ya pagados.

    El gráfico de análisis solo mostraba la deuda que queda por delante, así
    que los meses ya pagados desaparecían y no se veía el peso real que las
    cuotas tuvieron en cada mes. Acá cada mes trae la cuota COMPLETA
    programada (pagada o no) y, aparte, cuánto de eso ya está pagado.
    """
    hoy = date.today()
    deudas = list(Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'))

    pagos_por_deuda = {d.pk: {p.periodo: p for p in d.pagos.all()} for d in deudas}

    filas = []
    saldo_futuro = None
    for i in range(-atras, adelante + 1):
        f = date(hoy.year, hoy.month, 1) + relativedelta(months=i)
        periodo = f.year * 100 + f.month

        total = Decimal('0')
        pagado = Decimal('0')
        for d in deudas:
            if periodo not in d.periodos_programados:
                continue
            pago = pagos_por_deuda[d.pk].get(periodo)
            cuota = pago.monto if pago else d.monto_cuota_de(periodo)
            total += cuota
            if pago:
                pagado += cuota

        restante = Decimal('0')
        for d in deudas:
            for p in d.periodos_pendientes:
                if p > periodo:
                    restante += d.monto_cuota_de(p)

        filas.append({
            'periodo': periodo,
            'mes': f'{NOMBRES_MESES[f.month - 1]} {f.year}',
            'mes_corto': NOMBRES_MESES[f.month - 1],
            'total': float(total),
            'pagado': float(pagado),
            'pendiente': float(total - pagado),
            'restante': float(restante),
            'es_pasado': (f.year, f.month) < (hoy.year, hoy.month),
            'es_mes_actual': (f.year, f.month) == (hoy.year, hoy.month),
        })
    return filas

def pendientes_del_mes(usuario, year, month):
    """Todo lo que falta pagar en un mes, en una sola lista.

    Junta las tres cosas que se pagan: cuotas de compras a plazo,
    suscripciones y cuentas puntuales. Cada item trae lo que el template
    necesita para pintar la fila y su botón, sin ifs por tipo.
    """
    periodo = year * 100 + month
    items = []

    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if periodo not in d.periodos_programados:
            continue
        pago = next((p for p in d.pagos.all() if p.periodo == periodo), None)
        fecha = d.fecha_cobro_de(periodo)
        items.append({
            'tipo': 'cuota',
            'nombre': d.acreedor,
            'detalle': f'Cuota {d.periodos_programados.index(periodo) + 1} de {d.cuotas_totales}',
            'monto': pago.monto if pago else d.monto_cuota_de(periodo),
            'fecha': fecha,
            'pagado': bool(pago),
            'fecha_pago': pago.fecha_pago if pago else None,
            'icono': 'fa-credit-card',
            'url_pagar': f'/pagar-cuota/{d.pk}/',
            'url_anular': f'/anular-cuota/{d.pk}/',
            'periodo': periodo,
        })

    for s in Suscripcion.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if periodo not in s.periodos_programados:
            continue
        pago = next((p for p in s.pagos.all() if p.periodo == periodo), None)
        items.append({
            'tipo': 'servicio',
            'nombre': s.nombre,
            'detalle': f'Suscripción · se cobra el {s.dia_cobro}',
            'monto': s.monto,
            'fecha': s.fecha_cobro_de(periodo),
            'pagado': bool(pago),
            'fecha_pago': pago.fecha_pago if pago else None,
            'icono': 'fa-rotate',
            'marca': s.marca,
            'inicial': s.inicial,
            'url_pagar': f'/suscripciones/pagar/{s.pk}/',
            'url_anular': f'/suscripciones/anular-pago/{s.pk}/',
            'periodo': periodo,
        })

    for t in Transaccion.objects.filter(
            usuario=usuario, tipo='EGRESO', es_cuota=False, pagado=False,
            fecha__year=year, fecha__month=month,
    ).exclude(descripcion__startswith='Suscripción: ').exclude(
            descripcion__startswith='Pendiente: '):
        items.append({
            'tipo': 'gasto',
            'nombre': t.descripcion or t.get_categoria_display(),
            'detalle': t.get_categoria_display(),
            'monto': t.monto,
            'fecha': t.fecha,
            'pagado': False,
            'fecha_pago': None,
            'icono': t.icono,
            'url_pagar': f'/gasto/pagar/{t.pk}/',
            'url_anular': f'/gasto/anular-pago/{t.pk}/',
            'periodo': periodo,
        })

    _, ultimo = calendar.monthrange(year, month)
    for g in GastoPendiente.objects.filter(
            usuario=usuario,
            fecha_vencimiento__gte=date(year, month, 1),
            fecha_vencimiento__lte=date(year, month, ultimo)):
        items.append({
            'tipo': 'cuenta',
            'nombre': g.nombre,
            'detalle': g.categoria or 'Cuenta por pagar',
            'monto': g.monto,
            'fecha': g.fecha_vencimiento,
            'pagado': g.pagado,
            'fecha_pago': g.fecha_pago,
            'icono': 'fa-file-invoice',
            'url_pagar': f'/gasto-pendiente/pagar/{g.pk}/',
            'url_anular': f'/gasto-pendiente/anular/{g.pk}/',
            'periodo': periodo,
        })

    hoy = date.today()
    for it in items:
        it['atrasado'] = not it['pagado'] and it['fecha'] < hoy
    items.sort(key=lambda x: (x['pagado'], not x['atrasado'], x['fecha']))
    return items

def contadores(usuario, resumen_actual=None):
    """Contexto compartido por todas las pantallas.

    Los badges del menú, la salud del mes y los datos del panel de registro.
    El panel vive en base.html (los botones que lo abren están en el topbar
    de todas las pantallas), así que sus datos tienen que llegar a todas —
    antes solo existían en el contexto del dashboard.

    'resumen_actual' es el resumen del mes en curso si quien llama (el
    dashboard) ya lo calculó: evita que salud_financiera() vuelva a
    consultar lo mismo.
    """
    cuotas_activas = Deuda.objects.filter(
        usuario=usuario, cuotas_pagadas__lt=F('cuotas_totales')).count()
    personas = Persona.objects.filter(usuario=usuario).prefetch_related('prestamos__abonos')
    prestamos_activos = sum(len(p.prestamos_activos) for p in personas)
    total_por_cobrar = round(sum(p.total_pendiente for p in personas))
    hoy = date.today()
    datos = {
        'cuotas_activas': cuotas_activas,
        'prestamos_activos': prestamos_activos,
        'total_por_cobrar': total_por_cobrar,

        'profile': get_or_create_profile(usuario),

        'form_registro': TransaccionForm(initial={'tipo': 'EGRESO', 'fecha': hoy}),
        'hoy_iso': hoy.isoformat(),
        'cats_egreso': Categoria.opciones(usuario, 'EGRESO'),
        'cats_ingreso': Categoria.opciones(usuario, 'INGRESO'),
        'cats_egreso_json': [list(c) for c in Categoria.opciones(usuario, 'EGRESO')],
        'cats_ingreso_json': [list(c) for c in Categoria.opciones(usuario, 'INGRESO')],

        'subs_pendientes': sum(
            1 for s in Suscripcion.objects.filter(usuario=usuario, activa=True)
                                          .prefetch_related('pagos')
            if not s.pagada_este_mes
        ),
    }
    datos.update(salud_financiera(usuario, resumen_actual=resumen_actual))
    return datos

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
            es_mes_en_curso = (cursor.year, cursor.month) == (hoy.year, hoy.month)
            Transaccion.objects.create(
                usuario=usuario, tipo='EGRESO', monto=sub.monto,
                categoria=sub.categoria or 'Suscripciones',
                descripcion=f'Suscripción: {sub.nombre}',
                fecha=date(cursor.year, cursor.month, dia), es_cuota=False,
                pagado=not es_mes_en_curso,
                fecha_pago=None if es_mes_en_curso else date(cursor.year, cursor.month, dia),
            )
            sub.ultimo_mes_generado = cursor.year * 100 + cursor.month
            cursor = cursor + relativedelta(months=1)
            genero_algo = True

        if genero_algo:
            sub.save(update_fields=['ultimo_mes_generado'])

def _calendario_del_mes(year, month, hoy, eventos_por_dia):
    """La grilla de semanas del mes con los eventos de pago ya resueltos."""
    calendario_datos = []
    for semana in calendar.monthcalendar(year, month):
        fila = []
        for dia in semana:
            if dia == 0:
                fila.append(None)
            else:
                eventos = eventos_por_dia.get(dia, [])
                fila.append({
                    'numero': dia,
                    'es_hoy': (dia == hoy.day and month == hoy.month and year == hoy.year),
                    'eventos': eventos,
                    'tiene_pagos': bool(eventos),
                    'todo_pagado': bool(eventos) and all(e['estado'] == 'pagado' for e in eventos),
                    'total_dia': sum(float(e['monto']) for e in eventos),
                })
        calendario_datos.append(fila)
    dias_con_pago = [d for semana in calendario_datos for d in semana if d and d['tiene_pagos']]
    return calendario_datos, dias_con_pago

def _serie_seis_meses(usuario, hoy, year, month, resumen_actual):
    """Ingresos/gastos/cuotas de los últimos 6 meses, para el gráfico.

    Reusa 'resumen_actual' para el mes en curso en vez de recalcularlo: es
    la misma consulta que ya hizo dashboard() para 'r'.
    """
    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = [], [], [], []
    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        if f.year == year and f.month == month:
            rr = resumen_actual
        else:
            rr = resumen_mes(usuario, f.year, f.month)
        meses_labels.append(f"{NOMBRES_MESES[f.month - 1]} {f.year}")
        datos_ingresos.append(rr['ingresos'])
        datos_gastos.append(rr['gastos'])
        datos_cuotas.append(rr['total_cuotas_mes'])
    return meses_labels, datos_ingresos, datos_gastos, datos_cuotas

def _desglose_categorias(usuario, resumen):
    """Gasto por categoría del mes, con porcentaje y color para la dona."""
    gastos_categoria = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=resumen['fecha_inicio'], fecha__lte=resumen['fecha_fin'],
    ).values('categoria').annotate(total=Sum('monto')).order_by('-total')

    total_cat = sum(float(x['total']) for x in gastos_categoria) or 1.0
    etiquetas = dict(Transaccion.CATEGORIAS)
    categorias = []
    for x in gastos_categoria:
        cat = x['categoria'] or 'Otros'
        categorias.append({
            'nombre': cat,
            'label': etiquetas.get(cat, cat),
            'total': float(x['total']),
            'porcentaje': round(float(x['total']) / total_cat * 100),
            'color': Transaccion.COLORES_CATEGORIA.get(cat, Transaccion.COLORES_CATEGORIA['Otros']),
        })
    return categorias

def _mis_cuotas_detalle(usuario, hoy):
    """Cada deuda activa con su avance, para la tarjeta 'Debo en total'.

    Antes vivía dentro de dashboard() bajo el comentario original: el
    dashboard mostraba cuánto se paga ESTE mes y nada más, y faltaba la
    pregunta que la gente hace primero, cuánto debo en total.
    """
    mis_cuotas = []
    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if d.esta_saldada:
            continue
        atrasadas = len(d.periodos_atrasados)
        mis_cuotas.append({
            'obj': d,
            'acreedor': d.acreedor,
            'categoria': d.get_categoria_display(),
            'icono': Transaccion(categoria=d.categoria, tipo='EGRESO').icono,
            'color': Transaccion.COLORES_CATEGORIA.get(
                d.categoria, Transaccion.COLORES_CATEGORIA['Otros']),
            'monto_total': round(float(d.monto_total)),
            'pagado': round(float(d.monto_pagado)),
            'restante': round(float(d.monto_restante)),
            'cuota': round(float(d.monto_cuota)),
            'porcentaje': d.porcentaje,
            'cuotas_pagadas': d.cuotas_pagadas,
            'cuotas_totales': d.cuotas_totales,
            'restantes': d.cuotas_restantes,
            'periodo_a_pagar': d.periodo_a_pagar,
            'pagada_este_mes': d.esta_pagada_en(hoy.year * 100 + hoy.month),
            'atrasadas': atrasadas,
            'urgencia': d.urgencia,
            'texto_urgencia': d.texto_urgencia,
            'fin': d.fecha_fin_estimada,
        })
    mis_cuotas.sort(key=lambda x: (-x['atrasadas'], -x['restante']))
    deuda_pagada_total = sum(c['pagado'] for c in mis_cuotas)
    deuda_bruta_total = sum(c['monto_total'] for c in mis_cuotas)
    return mis_cuotas, deuda_pagada_total, deuda_bruta_total

def _proyecciones_deuda_activas(todas_las_deudas):
    """Cuándo termina de pagarse cada deuda activa, la más próxima primero."""
    proyecciones = []
    for d in todas_las_deudas:
        if d.esta_saldada:
            continue
        fin = d.fecha_fin_estimada
        proyecciones.append({
            'acreedor': d.acreedor,
            'fecha_fin': fin,
            'cuotas_restantes': d.cuotas_restantes,
            'monto_cuota': float(d.monto_cuota),
            'mes_fin': f'{NOMBRES_MESES[fin.month - 1]} {fin.year}',
        })
    proyecciones.sort(key=lambda x: x['fecha_fin'])
    return proyecciones

TONOS_INSIGHT = {
    'peligro': {'color': '#e25c5c', 'tenue': 'rgba(226,92,92,.14)',
                'borde': 'rgba(226,92,92,.32)', 'etiqueta': 'Urgente'},
    'alerta':  {'color': '#ffaa2c', 'tenue': 'rgba(255,170,44,.14)',
                'borde': 'rgba(255,170,44,.32)', 'etiqueta': 'Ojo con esto'},
    'exito':   {'color': '#53d258', 'tenue': 'rgba(83,210,88,.14)',
                'borde': 'rgba(83,210,88,.3)', 'etiqueta': 'Vas bien'},
    'info':    {'color': '#4b8cff', 'tenue': 'rgba(75,140,255,.14)',
                'borde': 'rgba(75,140,255,.28)', 'etiqueta': 'A este ritmo'},
}

def _insights_dashboard(resumen, datos_gastos, pendientes, proyecciones_deuda, presupuesto):
    """Las frases del bloque de avisos: presupuesto, variación mensual,
    cuotas urgentes y la proyección de la deuda más próxima a terminar."""
    insights = []
    presupuesto_pct = None
    if presupuesto and presupuesto.limite_mensual > 0:
        limite = float(presupuesto.limite_mensual)
        presupuesto_pct = round((resumen['gastos'] / limite) * 100)
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

    if proyecciones_deuda:
        prox = proyecciones_deuda[0]
        insights.append({
            'tipo': 'info', 'icono': 'fa-check-circle',
            'texto': f'A este ritmo, terminas de pagar {prox["acreedor"]} en {prox["mes_fin"]}.',
        })

    for i in insights:
        i.update(TONOS_INSIGHT.get(i['tipo'], TONOS_INSIGHT['info']))

    return insights, presupuesto_pct

def _primeros_pasos(usuario):
    """Lista de arranque de una cuenta nueva.

    No hay campo ni tabla nueva: cada punto se marca solo mirando si el dato
    ya existe. Así la lista dice la verdad aunque el usuario haya cargado sus
    cosas antes de ver el tour, y no queda estado que mantener.
    """
    pasos = [
        {'titulo': 'Anota lo que entra',
         'nota': 'Tu sueldo o ingreso del mes',
         'icono': 'fa-arrow-down',
         'hecho': Transaccion.objects.filter(usuario=usuario, tipo='INGRESO').exists(),
         'url': '#', 'abrir': '#modalGasto', 'preset': 'INGRESO'},
        {'titulo': 'Anota un gasto',
         'nota': 'Para que el saldo del mes sea real',
         'icono': 'fa-plus',
         'hecho': Transaccion.objects.filter(usuario=usuario, tipo='EGRESO').exists(),
         'url': '#', 'abrir': '#modalGasto', 'preset': 'EGRESO'},
        {'titulo': 'Agrega tus compras en cuotas',
         'nota': 'La cuota queda puesta en cada mes',
         'icono': 'fa-credit-card',
         'hecho': Deuda.objects.filter(usuario=usuario).exists(),
         'url': reverse('deudas')},
        {'titulo': 'Suma tus suscripciones',
         'nota': 'Se cobran solas cada mes',
         'icono': 'fa-rotate',
         'hecho': Suscripcion.objects.filter(usuario=usuario).exists(),
         'url': reverse('suscripciones')},
        {'titulo': 'Crea una meta de ahorro',
         'nota': 'Cuánto juntar y para cuándo',
         'icono': 'fa-bullseye',
         'hecho': MetaAhorro.objects.filter(usuario=usuario).exists(),
         'url': reverse('metas')},
        {'titulo': 'Pon tu presupuesto del mes',
         'nota': 'Un techo para el día a día',
         'icono': 'fa-gauge-high',
         'hecho': Presupuesto.objects.filter(usuario=usuario).exists(),
         'url': reverse('perfil')},
    ]
    return pasos, sum(1 for p in pasos if p['hecho'])

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
    nombre_mes = nombre_mes_es(year, month)
    todas_las_deudas = Deuda.objects.filter(usuario=request.user)

    calendario_datos, dias_con_pago = _calendario_del_mes(year, month, hoy, r['eventos'])
    meses_labels, datos_ingresos, datos_gastos, datos_cuotas = _serie_seis_meses(
        request.user, hoy, year, month, r)
    categorias = _desglose_categorias(request.user, r)

    pendientes = [d for d in todas_las_deudas
                  if not d.esta_saldada and d.dias_para_vencer is not None]
    pendientes.sort(key=lambda d: d.dias_para_vencer)
    proximo_pago = pendientes[0] if pendientes else None

    pagos_mes = pendientes_del_mes(request.user, year, month)
    sin_pagar = [i for i in pagos_mes if not i['pagado']]
    atrasados = [i for i in sin_pagar if i['atrasado']]

    mis_cuotas, deuda_pagada_total, deuda_bruta_total = _mis_cuotas_detalle(request.user, hoy)

    ultimas = Transaccion.objects.filter(usuario=request.user).order_by('-fecha', '-id')[:10]
    deuda_total = sum(float(d.monto_restante) for d in todas_las_deudas if not d.esta_saldada)
    metas = MetaAhorro.objects.filter(usuario=request.user)
    es_nuevo = (r['ingresos'] == 0 and r['gastos'] == 0 and not todas_las_deudas.exists())

    presupuesto = Presupuesto.objects.filter(usuario=request.user).first()
    proyecciones_deuda = _proyecciones_deuda_activas(todas_las_deudas)
    insights, presupuesto_pct = _insights_dashboard(
        r, datos_gastos, pendientes, proyecciones_deuda, presupuesto)
    se_libera = proyecciones_deuda[0] if proyecciones_deuda else None

    context = {
        'nombre_mes': nombre_mes,
        'es_nuevo': es_nuevo,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'es_mes_actual': (year, month) == (hoy.year, hoy.month),
        'prev_month_nombre': nombre_mes_es(prev_year, prev_month),
        'next_month_nombre': nombre_mes_es(next_year, next_month),
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],

        'total_ingresos': round(r['ingresos']),
        'total_gastos': round(r['gastos']),
        'total_cuotas_mes': round(r['total_cuotas_mes']),
        'cuotas_pagadas_mes': round(r['cuotas_pagadas_mes']),
        'cuotas_pendientes_mes': round(r['cuotas_pendientes_mes']),
        'ya_gaste': round(r['gastos']),
        'gastos_pagados': round(r['gastos_pagados']),
        'gastos_por_pagar': round(r['gastos_por_pagar']),
        'pct_gasto_pagado': (round(r['gastos_pagados'] / r['gastos'] * 100)
                             if r['gastos'] else 0),
        'total_comprometido_mes': round(r['comprometido']),
        'disponible': round(r['disponible']),

        'atrasado_arrastrado': round(r['atrasado_arrastrado']),
        'cuotas_arrastradas': r['cuotas_arrastradas'],
        'n_cuotas_arrastradas': len(r['cuotas_arrastradas']),
        'deuda_total': round(deuda_total),

        'mis_cuotas': mis_cuotas,
        'deuda_bruta_total': deuda_bruta_total,
        'deuda_pagada_total': deuda_pagada_total,
        'deuda_pct_pagado': (round(deuda_pagada_total / deuda_bruta_total * 100)
                             if deuda_bruta_total else 0),
        'cuota_mensual_total': round(sum(c['cuota'] for c in mis_cuotas)),
        'cuotas_atrasadas_total': sum(c['atrasadas'] for c in mis_cuotas),

        'fijo_mensual': round(
            sum(c['cuota'] for c in mis_cuotas)
            + sum(float(s.monto) for s in Suscripcion.objects.filter(
                usuario=request.user, activa=True))
        ),

        'por_pagar': round(r['cuotas_pendientes_mes'] + r['servicios_pendientes_mes']),
        'servicios_pendientes_mes': round(r['servicios_pendientes_mes']),
        'servicios_pagados_mes': round(r['servicios_pagados_mes']),
        'dias_restantes': r['dias_restantes'],
        'por_dia': round(r['por_dia']),
        'pct_gastado': r['pct_gastado'],
        'pct_por_pagar': r['pct_por_pagar'],
        'pct_disponible': r['pct_disponible'],
        'proximo_pago': proximo_pago,
        'se_libera': se_libera,
        'categorias': categorias,
        'dias_con_pago': dias_con_pago,

        'pendientes': pagos_mes,
        'pendientes_sin_pagar': sin_pagar,
        'pendientes_atrasados': atrasados,
        'monto_sin_pagar': round(sum(float(i['monto']) for i in sin_pagar)),
        'monto_ya_pagado': round(sum(float(i['monto']) for i in pagos_mes if i['pagado'])),
        'mes_al_dia': bool(pagos_mes) and not sin_pagar,

        'insights': insights,
        'presupuesto': presupuesto,
        'presupuesto_pct': presupuesto_pct,
        'proyecciones_deuda': proyecciones_deuda,
        'deudas': [e['deuda'] for dia in r['eventos'].values() for e in dia],
        'gastos_pendientes': GastoPendiente.objects.filter(usuario=request.user, pagado=False),
        'ultimas': ultimas,
        'metas': metas,
        'calendario': calendario_datos,

        'abrir_panel': bool(request.GET.get('registrar')),

        'meses_json': meses_labels,
        'ingresos_json': datos_ingresos,
        'gastos_json': datos_gastos,
        'cuotas_json': datos_cuotas,
        'cat_labels_json': [c['label'] for c in categorias],
        'cat_data_json': [c['total'] for c in categorias],
        'cat_colores_json': [c['color'] for c in categorias],
    }

    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    context['hoy_texto'] = (f'{dias_semana[hoy.weekday()]}, {hoy.day} '
                            f'{MESES_LARGOS[hoy.month - 1]} {hoy.year}')

    f_ant = date(year, month, 1) - relativedelta(months=1)
    r_ant = resumen_mes(request.user, f_ant.year, f_ant.month)
    saldo_ant = r_ant['disponible']
    if saldo_ant:
        var_saldo = round((r['disponible'] - saldo_ant) / abs(saldo_ant) * 100)
        context['variacion_saldo'] = var_saldo
        context['variacion_saldo_abs'] = abs(var_saldo)
    else:
        context['variacion_saldo'] = None
        context['variacion_saldo_abs'] = None
    context['mes_anterior_nombre'] = MESES_LARGOS[f_ant.month - 1]

    pasos, pasos_hechos = _primeros_pasos(request.user)
    context['primeros_pasos'] = pasos if pasos_hechos < len(pasos) else None
    context['pasos_hechos'] = pasos_hechos
    context['pasos_total'] = len(pasos)
    context['pasos_pct'] = int(pasos_hechos * 100 / len(pasos))

    context['mapa_categorias'] = Categoria.mapa(request.user)
    context.update(contadores(
        request.user,
        resumen_actual=r if (year, month) == (hoy.year, hoy.month) else None,
    ))
    return render(request, 'finanzas/dashboard.html', context)

@login_required(login_url='/login/')
def deudas(request):
    """Pantalla propia para las compras en cuotas.

    Antes las deudas solo se veían dentro del dashboard, mezcladas con todo
    lo demás, y no había dónde ver el avance de cada una.
    """
    lista = list(Deuda.objects.filter(usuario=request.user).prefetch_related('pagos'))
    activas = [d for d in lista if not d.esta_saldada]

    activas.sort(key=lambda d: (
        -len(d.periodos_atrasados),
        d.dias_para_vencer if d.dias_para_vencer is not None else 9999,
    ))
    saldadas = [d for d in lista if d.esta_saldada]

    proximas = [d for d in activas if d.dias_para_vencer is not None]
    proximas.sort(key=lambda d: d.fecha_fin_estimada)

    context = {
        'deudas': activas,
        'saldadas': sorted(saldadas, key=lambda d: d.fecha_fin_estimada, reverse=True),
        'total_saldado': round(sum(float(d.monto_total) for d in saldadas)),
        'deudas_activas': len(activas),
        'total_cuotas_mes': round(sum(float(d.monto_cuota) for d in activas)),
        'total_restante': round(sum(float(d.monto_restante) for d in lista)),
        'total_pagado': round(sum(float(d.monto_pagado) for d in lista)),
        'total_atrasado': round(sum(float(d.monto_atrasado) for d in activas)),
        'cuotas_atrasadas': sum(len(d.periodos_atrasados) for d in activas),
        'total_deuda': round(sum(float(d.monto_total) for d in lista)),
        'se_libera': proximas[0] if proximas else None,
        'form': DeudaForm(),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/deudas.html', context)

@login_required(login_url='/login/')
def pagar_cuota(request, deuda_id):
    """Registra el pago de UNA cuota, atado al mes que le corresponde.

    Por defecto paga el mes pendiente más antiguo: es lo que espera
    cualquiera que deba plata, y evita huecos en el historial. Se puede
    pasar 'periodo' en el POST para pagar un mes concreto (el calendario
    del dashboard lo hace).
    """
    if request.method != 'POST':
        return _redirigir(request)

    deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def responder(ok, msg, nivel='success'):
        if es_ajax:
            datos = {'ok': ok, 'msg': msg}
            if ok:
                datos.update({
                    'acreedor': deuda.acreedor,
                    'cuotas_pagadas': deuda.pagos.count(),
                    'cuotas_totales': deuda.cuotas_totales,
                    'porcentaje': deuda.porcentaje,
                    'terminada': deuda.esta_saldada,
                    'restante': str(deuda.monto_restante),
                    'texto_urgencia': deuda.texto_urgencia,
                })
            return JsonResponse(datos)
        getattr(messages, nivel)(request, msg)
        return _redirigir(request)

    try:
        periodo = int(request.POST.get('periodo') or 0) or deuda.periodo_a_pagar
    except (ValueError, TypeError):
        periodo = deuda.periodo_a_pagar

    if periodo is None:
        return responder(False, f'{deuda.acreedor} ya está pagada por completo.', 'warning')
    if periodo not in deuda.periodos_programados:
        return responder(False, 'Ese mes no corresponde a esta compra.', 'warning')
    if deuda.esta_pagada_en(periodo):
        return responder(False, 'Esa cuota ya estaba pagada.', 'warning')

    monto = deuda.monto_cuota_de(periodo)
    fecha_cobro = deuda.fecha_cobro_de(periodo)
    hoy = timezone.localdate()
    numero = deuda.periodos_programados.index(periodo) + 1

    tx = Transaccion.objects.create(
        usuario=request.user, tipo='EGRESO', monto=monto,
        categoria=deuda.categoria,
        descripcion=f'Cuota {numero}/{deuda.cuotas_totales} — {deuda.acreedor}',
        fecha=fecha_cobro, es_cuota=True,
        pagado=True, fecha_pago=hoy,
    )
    PagoCuota.objects.create(
        deuda=deuda, periodo=periodo, monto=monto, fecha_pago=hoy, transaccion=tx,
    )

    deuda.cuotas_pagadas = deuda.pagos.count()
    deuda.save(update_fields=['cuotas_pagadas'])

    if deuda.esta_saldada:
        msg = f'{deuda.acreedor} quedó pagada por completo.'
    else:
        nombres = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                   'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        etiqueta = f'{nombres[periodo % 100 - 1]} {periodo // 100}'
        restantes = len(deuda.periodos_pendientes)
        msg = (f'Cuota de {etiqueta} pagada. '
               f'Te queda{"n" if restantes != 1 else ""} {restantes} '
               f'cuota{"s" if restantes != 1 else ""}.')
    return responder(True, msg)

@login_required(login_url='/login/')
def anular_cuota(request, deuda_id):
    """Deshace el pago de una cuota y borra su movimiento.

    Antes buscaba la transacción por texto (descripcion__icontains=acreedor),
    lo que podía borrar la cuota de otra deuda de nombre parecido ("Visa" y
    "Visa Oro"). Ahora el pago apunta a su propia transacción, así que se
    borra exactamente la que corresponde.
    """
    if request.method != 'POST':
        return _redirigir(request)

    deuda = get_object_or_404(Deuda, pk=deuda_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        periodo = int(request.POST.get('periodo') or 0)
    except (ValueError, TypeError):
        periodo = 0

    pago = (deuda.pagos.filter(periodo=periodo).first() if periodo
            else deuda.pagos.order_by('-periodo').first())

    if not pago:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
        messages.warning(request, 'No hay pagos que anular.')
        return _redirigir(request)

    etiqueta = pago.etiqueta_mes
    if pago.transaccion:
        pago.transaccion.delete()
    pago.delete()

    deuda.cuotas_pagadas = deuda.pagos.count()
    deuda.save(update_fields=['cuotas_pagadas'])

    if es_ajax:
        return JsonResponse({
            'ok': True, 'acreedor': deuda.acreedor,
            'cuotas_pagadas': deuda.cuotas_pagadas,
            'cuotas_totales': deuda.cuotas_totales,
            'porcentaje': deuda.porcentaje,
            'restante': str(deuda.monto_restante),
            'texto_urgencia': deuda.texto_urgencia,
        })
    messages.success(request, f'Se anuló la cuota de {etiqueta} de {deuda.acreedor}.')
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

@login_required(login_url='/login/')
def registrar_transaccion(request):
    tipo_inicial = request.GET.get('tipo', 'INGRESO')
    if request.method == 'POST':
        form = TransaccionForm(request.POST, usuario=request.user)
        if form.is_valid():
            t = form.save(commit=False)
            t.usuario = request.user
            marcado_pendiente = (request.POST.get('sin_pagar')
                                 or request.POST.get('es_pendiente'))
            if t.tipo == 'EGRESO' and marcado_pendiente:
                t.pagado = False
                t.fecha_pago = None
            else:
                t.pagado = True
                t.fecha_pago = t.fecha
            t.save()
            if t.tipo == 'EGRESO' and not t.pagado:
                messages.success(request, 'Gasto anotado como pendiente de pago.')
            else:
                messages.success(request, f'{"Ingreso" if t.es_ingreso else "Gasto"} registrado.')
            return _redirigir(request)

        for campo, errores in form.errors.items():
            etiqueta = form.fields[campo].label or campo
            messages.warning(request, f'{etiqueta}: {errores[0]}')
        if request.POST.get('next'):
            return _redirigir(request)
        tipo_inicial = request.POST.get('tipo', tipo_inicial)
    else:
        form = TransaccionForm(initial={'tipo': tipo_inicial, 'fecha': timezone.localdate()})

    context = {'form': form, 'tipo_inicial': tipo_inicial}
    context.update(contadores(request.user))
    return render(request, 'finanzas/form_transaccion.html', context)

@login_required(login_url='/login/')
def editar_transaccion(request, transaccion_id):
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    if request.method == 'POST':
        form = TransaccionForm(request.POST, instance=t, usuario=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Movimiento actualizado.')
            return _redirigir(request)
    else:
        form = TransaccionForm(instance=t, usuario=request.user)
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
def pagar_gasto(request, transaccion_id):
    """Marca un gasto único como pagado.

    No mueve montos: el gasto ya estaba contado en el mes. Solo registra que
    la plata salió, para que "ya gastaste" no mezcle lo pagado con lo que
    sigues debiendo.
    """
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return _redirigir(request)

    if not t.es_gasto_unico:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'Solo aplica a gastos.'})
        messages.warning(request, 'Eso no es un gasto que se marque a mano.')
        return _redirigir(request)

    if not t.pagado:
        t.pagado = True
        t.fecha_pago = timezone.localdate()
        t.save(update_fields=['pagado', 'fecha_pago'])

    if es_ajax:
        return JsonResponse({'ok': True, 'pagado': True,
                             'texto': t.texto_estado_pago})
    messages.success(request, f'{t.descripcion or t.get_categoria_display()}: marcado como pagado.')
    return _redirigir(request)

@login_required(login_url='/login/')
def anular_pago_gasto(request, transaccion_id):
    """Devuelve un gasto a 'sin pagar'."""
    t = get_object_or_404(Transaccion, id=transaccion_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return _redirigir(request)

    if t.pagado and t.es_gasto_unico:
        t.pagado = False
        t.fecha_pago = None
        t.save(update_fields=['pagado', 'fecha_pago'])

    if es_ajax:
        return JsonResponse({'ok': True, 'pagado': False})
    messages.success(request, 'Marcado como no pagado.')
    return _redirigir(request)

@login_required(login_url='/login/')
def registrar_ingreso(request):
    return redirect('/registrar/?tipo=INGRESO')

@login_required(login_url='/login/')
def estadisticas(request):
    hoy = date.today()
    activas = [d for d in Deuda.objects.filter(usuario=request.user)
                                        .prefetch_related('pagos') if not d.esta_saldada]

    labels = [d.acreedor for d in activas]
    data_cuota = [float(d.monto_cuota) for d in activas]
    data_restante = [float(d.monto_restante) for d in activas]

    meses, ingresos, gastos = [], [], []
    resumen_actual = None
    for i in range(11, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        r = resumen_mes(request.user, f.year, f.month)
        if i == 0:
            resumen_actual = r
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
        'labels_json': labels,
        'data_json': data_cuota,
        'data_restante_json': data_restante,
        'meses_json': meses,
        'ingresos_json': ingresos,
        'gastos_json': gastos,
        'promedio_gasto': round(promedio),
        'mejor_mes': meses[mejor] if mejor is not None else None,
        'mejor_ahorro': round(ahorros[mejor]) if mejor is not None else 0,
        'peor_mes': meses[peor] if peor is not None else None,
        'peor_gasto': round(gastos[peor]) if peor is not None else 0,
        'tasa_ahorro': tasa_ahorro,
        'ranking': ranking,
    }
    context.update(contadores(request.user, resumen_actual=resumen_actual))
    return render(request, 'finanzas/estadisticas.html', context)

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
    personas = list(Persona.objects.filter(usuario=request.user)
                    .prefetch_related('prestamos__abonos'))

    persona = next((p for p in personas if p.id == persona_id), None)
    if persona is None:
        raise Http404('Persona no encontrada')

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
    circunferencia = 327
    riesgo_offset = circunferencia - (circunferencia * analisis['riesgo_score'] / 100)

    serie = serie_cuotas(request.user, atras=6, adelante=6)
    indice_actual = next((i for i, f in enumerate(serie) if f['es_mes_actual']), 0)

    context = {
        'analisis': analisis,
        'simbolo': _simbolo_moneda(request.user),
        'riesgo_offset': round(riesgo_offset, 1),
        'serie': serie,
        'cuotas_atrasadas': analisis.get('cuotas_atrasadas', 0),
        'monto_atrasado': analisis.get('monto_atrasado', 0),
        'indice_actual': indice_actual,
        'total_pagado_serie': round(sum(f['pagado'] for f in serie)),
        'total_pendiente_serie': round(sum(f['pendiente'] for f in serie)),
        'serie_meses_json': [f['mes'] for f in serie],
        'serie_pagado_json': [round(f['pagado']) for f in serie],
        'serie_pendiente_json': [round(f['pendiente']) for f in serie],
        'serie_total_json': [round(f['total']) for f in serie],
        'serie_restante_json': [round(f['restante']) for f in serie],
        'proy_meses_json': [p['mes'] for p in analisis['proyeccion']],
        'proy_deuda_json': [p['deuda'] for p in analisis['proyeccion']],
        'proy_pago_json': [p['pago_mes'] for p in analisis['proyeccion']],
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/analisis.html', context)

@login_required(login_url='/login/')
@limitar(6, 3600, 'Ya pediste varias interpretaciones esta hora. '
                  'Los números de la pantalla no dependen de la IA.')
def analisis_ia(request):
    """Endpoint AJAX: genera la interpretación con IA (puede tardar unos segundos)."""
    from .analisis import analizar_finanzas
    from .ia import interpretar_con_ia

    perfil_usuario = get_or_create_profile(request.user)
    if not perfil_usuario.analisis_ia:
        return JsonResponse({'ok': False, 'msg': 'Tienes el analisis con IA desactivado.',
                             'desactivado': True})

    analisis = analizar_finanzas(request.user)
    interpretacion = interpretar_con_ia(analisis, _simbolo_moneda(request.user))
    if interpretacion:
        return JsonResponse({'ok': True, 'ia': interpretacion})
    return JsonResponse({'ok': False, 'msg': 'IA no disponible'})

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
            fecha=venc, es_cuota=False, pagado=False,
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
        if gasto.transaccion:
            gasto.transaccion.pagado = True
            gasto.transaccion.fecha_pago = gasto.fecha_pago
            gasto.transaccion.save(update_fields=['pagado', 'fecha_pago'])
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
        if gasto.transaccion:
            gasto.transaccion.pagado = False
            gasto.transaccion.fecha_pago = None
            gasto.transaccion.save(update_fields=['pagado', 'fecha_pago'])
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

@login_required(login_url='/login/')
def suscripciones(request):
    """Lista de suscripciones (activas e inactivas)."""
    subs = list(Suscripcion.objects.filter(usuario=request.user).prefetch_related('pagos'))
    activas = [s for s in subs if s.activa]
    total_mensual = sum(float(s.monto) for s in activas)

    orden = {'atrasada': 0, 'pendiente': 1, 'pagada': 2, 'pausada': 3}
    subs.sort(key=lambda s: (orden.get(s.estado_mes, 9), s.nombre))

    pendientes = [s for s in activas if not s.pagada_este_mes]
    atrasadas = [s for s in activas if s.periodos_atrasados]

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
        'pendientes_mes': len(pendientes),
        'monto_pendiente_mes': round(sum(float(s.monto) for s in pendientes)),
        'monto_pagado_mes': round(sum(float(s.monto) for s in activas if s.pagada_este_mes)),
        'atrasadas': len(atrasadas),
        'monto_atrasado': round(sum(float(s.monto_atrasado) for s in atrasadas)),
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
def pagar_servicio(request, sub_id):
    """Marca el mes de una suscripción como pagado.

    Por defecto paga el mes pendiente más antiguo, igual que las cuotas: así
    ponerse al día no deja huecos. No crea transacción — el cobro ya se
    registró como gasto cuando llegó el mes.
    """
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def responder(ok, msg, nivel='success'):
        if es_ajax:
            datos = {'ok': ok, 'msg': msg}
            if ok:
                datos.update({
                    'nombre': sub.nombre,
                    'estado': sub.estado_mes,
                    'texto_estado': sub.texto_estado,
                    'texto_a_pagar': sub.texto_a_pagar,
                    'pagada_este_mes': sub.pagada_este_mes,
                })
            return JsonResponse(datos)
        getattr(messages, nivel)(request, msg)
        return _redirigir(request, 'suscripciones')

    if request.method != 'POST':
        return _redirigir(request, 'suscripciones')

    try:
        periodo = int(request.POST.get('periodo') or 0) or sub.periodo_a_pagar
    except (ValueError, TypeError):
        periodo = sub.periodo_a_pagar

    if periodo is None:
        return responder(False, f'{sub.nombre} ya está al día.', 'warning')
    if periodo not in sub.periodos_programados:
        return responder(False, 'Ese mes todavía no se ha cobrado.', 'warning')
    if sub.esta_pagada_en(periodo):
        return responder(False, 'Ese mes ya estaba pagado.', 'warning')

    hoy = timezone.localdate()
    PagoServicio.objects.create(
        suscripcion=sub, periodo=periodo, monto=sub.monto, fecha_pago=hoy,
    )
    Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO', es_cuota=False,
        descripcion=f'Suscripción: {sub.nombre}',
        fecha__year=periodo // 100, fecha__month=periodo % 100,
    ).update(pagado=True, fecha_pago=hoy)

    restantes = len(sub.periodos_pendientes)
    if restantes:
        msg = (f'{sub.nombre}: mes pagado. '
               f'Te queda{"n" if restantes != 1 else ""} {restantes} sin pagar.')
    else:
        msg = f'{sub.nombre} quedó al día.'
    return responder(True, msg)

@login_required(login_url='/login/')
def anular_pago_servicio(request, sub_id):
    """Deshace el pago de un mes de la suscripción."""
    sub = get_object_or_404(Suscripcion, id=sub_id, usuario=request.user)
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return _redirigir(request, 'suscripciones')

    try:
        periodo = int(request.POST.get('periodo') or 0)
    except (ValueError, TypeError):
        periodo = 0

    pago = (sub.pagos.filter(periodo=periodo).first() if periodo
            else sub.pagos.order_by('-periodo').first())

    if not pago:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
        messages.warning(request, 'No hay pagos que anular.')
        return _redirigir(request, 'suscripciones')

    etiqueta = pago.etiqueta_mes
    Transaccion.objects.filter(
        usuario=request.user, tipo='EGRESO', es_cuota=False,
        descripcion=f'Suscripción: {sub.nombre}',
        fecha__year=pago.periodo // 100, fecha__month=pago.periodo % 100,
    ).update(pagado=False, fecha_pago=None)
    pago.delete()

    if es_ajax:
        return JsonResponse({'ok': True, 'estado': sub.estado_mes,
                             'texto_estado': sub.texto_estado})
    messages.success(request, f'{sub.nombre}: se anuló el pago de {etiqueta}.')
    return _redirigir(request, 'suscripciones')

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

@login_required(login_url='/login/')
def categorias(request):
    """Gestión de categorías: las base y las propias, con lo gastado en cada
    una este mes.

    El número al lado de cada categoría es lo que hace útil la pantalla: sin
    él es una lista de etiquetas, con él se ve de inmediato cuáles usas y
    cuáles no sirven de nada.
    """
    hoy = date.today()
    _, ultimo = calendar.monthrange(hoy.year, hoy.month)
    inicio, fin = date(hoy.year, hoy.month, 1), date(hoy.year, hoy.month, ultimo)

    gastado = {
        x['categoria']: float(x['total'])
        for x in Transaccion.objects.filter(
            usuario=request.user, fecha__gte=inicio, fecha__lte=fin,
        ).values('categoria').annotate(total=Sum('monto'))
    }
    usos = {
        x['categoria']: x['n']
        for x in Transaccion.objects.filter(usuario=request.user)
                                    .values('categoria').annotate(n=Count('id'))
    }

    mapa = Categoria.mapa(request.user)
    propias_qs = list(Categoria.objects.filter(usuario=request.user))
    propias_slugs = {c.slug for c in propias_qs}

    def fila(slug, datos, obj=None):
        return {
            'slug': slug, 'label': datos['label'], 'color': datos['color'],
            'icono': datos['icono'], 'propia': datos['propia'],
            'gastado': round(gastado.get(slug, 0)),
            'usos': usos.get(slug, 0),
            'obj': obj,
        }

    de_gasto, de_ingreso = [], []
    slugs_ingreso = {c[0] for c in Transaccion.CATEGORIAS_INGRESO}

    for slug, datos in mapa.items():
        if slug in propias_slugs:
            continue
        destino = de_ingreso if slug in slugs_ingreso else de_gasto
        destino.append(fila(slug, datos))

    for c in propias_qs:
        destino = de_ingreso if c.tipo == "INGRESO" else de_gasto
        destino.append(fila(c.slug, mapa[c.slug], obj=c))

    de_gasto.sort(key=lambda x: -x["gastado"])
    de_ingreso.sort(key=lambda x: -x["gastado"])

    context = {
        'de_gasto': de_gasto,
        'de_ingreso': de_ingreso,
        'total_propias': len(propias_qs),
        'sin_usar': [c for c in de_gasto + de_ingreso if c['usos'] == 0],
        'paleta': Categoria.PALETA,
        'iconos': Categoria.ICONOS,
        'nombre_mes': nombre_mes_es(hoy.year, hoy.month),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/categorias.html', context)

@login_required(login_url='/login/')
def crear_categoria(request):
    if request.method != 'POST':
        return redirect('categorias')

    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        messages.warning(request, 'Ponle un nombre a la categoría.')
        return redirect('categorias')

    Categoria.objects.create(
        usuario=request.user, nombre=nombre,
        tipo=request.POST.get('tipo', 'EGRESO'),
        color=request.POST.get('color', '#ffaa2c'),
        icono=request.POST.get('icono', 'fa-tag'),
    )
    messages.success(request, 'Categoría "' + nombre + '" creada.')
    return redirect('categorias')

@login_required(login_url='/login/')
def editar_categoria(request, cat_id):
    cat = get_object_or_404(Categoria, id=cat_id, usuario=request.user)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            cat.nombre = nombre
        cat.color = request.POST.get('color', cat.color)
        cat.icono = request.POST.get('icono', cat.icono)
        cat.save(update_fields=['nombre', 'color', 'icono'])
        messages.success(request, 'Categoría actualizada.')
    return redirect('categorias')

@login_required(login_url='/login/')
def eliminar_categoria(request, cat_id):
    """Borra una categoría propia y mueve sus movimientos a "Otros".

    Si se borrara sin más, los movimientos quedarían con un slug que ya no
    existe: aparecerían sin nombre ni color en toda la app.
    """
    cat = get_object_or_404(Categoria, id=cat_id, usuario=request.user)
    if request.method == 'POST':
        nombre = cat.nombre
        destino = 'Otros_Ingresos' if cat.tipo == 'INGRESO' else 'Otros'
        movidos = Transaccion.objects.filter(
            usuario=request.user, categoria=cat.slug,
        ).update(categoria=destino)
        cat.delete()
        if movidos:
            messages.success(
                request, '"' + nombre + '" eliminada. "' + str(movidos)
                + ' movimiento(s) pasaron a Otros.')
        else:
            messages.success(request, '"' + nombre + '" eliminada.')
    return redirect('categorias')

@login_required(login_url='/login/')
def metas(request):
    """Pantalla propia para las metas, con el avance mes a mes.

    Antes las metas solo se veían como barras en el dashboard: se sabía
    cuánto falta, pero no si se está aportando o si la meta lleva meses
    quieta — que es la diferencia entre una meta viva y una abandonada.
    """
    hoy = date.today()
    lista = list(MetaAhorro.objects.filter(usuario=request.user)
                                   .prefetch_related('aportes'))

    meses = []
    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        meses.append({'clave': f.year * 100 + f.month,
                      'label': NOMBRES_MESES[f.month - 1]})

    datos = []
    for meta in lista:
        aportes = list(meta.aportes.all())
        por_mes = {}
        for ap in aportes:
            k = ap.fecha.year * 100 + ap.fecha.month
            por_mes[k] = por_mes.get(k, 0) + float(ap.monto)

        serie = [por_mes.get(m['clave'], 0) for m in meses]
        techo = max(serie) or 1
        ultimo = aportes[0] if aportes else None
        datos.append({
            'meta': meta,
            'serie': [{'label': meses[i]['label'],
                       'monto': round(serie[i]),
                       'alto': round(serie[i] / techo * 100)}
                      for i in range(len(meses))],
            'aportado_6m': round(sum(serie)),
            'promedio_mes': round(sum(serie) / len([s for s in serie if s]) ) if any(serie) else 0,
            'ultimo_aporte': ultimo,
            'meses_quieta': (((hoy.year - ultimo.fecha.year) * 12
                              + hoy.month - ultimo.fecha.month)
                             if ultimo else None),
        })

    datos.sort(key=lambda d: (d['meta'].esta_completa, -float(d['meta'].porcentaje)))

    context = {
        'metas_datos': datos,
        'labels_meses': [m['label'] for m in meses],
        'total_ahorrado': round(sum(float(m.monto_actual) for m in lista)),
        'total_meta': round(sum(float(m.monto_meta) for m in lista)),
        'total_faltante': round(sum(float(m.monto_faltante) for m in lista)),
        'completas': len([m for m in lista if m.esta_completa]),
        'form': MetaAhorroForm(),
    }
    context.update(contadores(request.user))
    return render(request, 'finanzas/metas.html', context)

@login_required(login_url='/login/')
def exportar_excel(request):
    """Movimientos en Excel, agrupados por mes y con formato.

    Si openpyxl no está instalado devuelve el CSV en su lugar en vez de
    reventar con un 500: el botón del perfil es el mismo, y en un hosting
    donde falte la librería es mejor entregar el archivo crudo que nada.
    """
    hoy = timezone.localdate()
    cuenta = request.user.get_username()

    try:
        contenido = exportar.libro_excel(request.user, cuenta, hoy)
    except ImportError:
        return exportar_csv(request)

    response = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    archivo = f'Rekon_movimientos_{hoy:%Y-%m-%d}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{archivo}"'
    return response

@login_required(login_url='/login/')
def exportar_csv(request):
    """El mismo contenido en texto plano, para quien quiera el archivo crudo.

    Un CSV no admite color, negrita ni ancho de columna: las bandas de mes
    son filas de texto y los subtotales, filas normales.
    """
    hoy = timezone.localdate()
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    archivo = f'Rekon_movimientos_{hoy:%Y-%m-%d}.csv'
    response['Content-Disposition'] = f'attachment; filename="{archivo}"'
    exportar.escribir_csv(csv.writer(response, delimiter=';'),
                          request.user, request.user.get_username(), hoy)
    return response

@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    """Sirve static/js/sw.js desde la raiz del sitio.

    El alcance de un service worker no puede subir de la carpeta donde vive el
    archivo. En /static/js/sw.js solo controlaria /static/js/, que no es
    ninguna pantalla de la app: Chrome registraria el worker y aun asi no
    ofreceria instalar. Servido desde /sw.js el alcance es todo el sitio.

    La alternativa era mandar el encabezado Service-Worker-Allowed desde el
    servidor de estaticos, pero eso depende de la configuracion del hosting y
    esto no.

    Sin cache (no_store): si el navegador guardara este archivo, una version
    con un error quedaria fija y no habria manera de reemplazarla.
    """
    ruta = finders.find('js/sw.js')
    if not ruta:
        raise Http404('sw.js no encontrado')
    with open(ruta, 'rb') as f:
        contenido = f.read()
    return HttpResponse(contenido, content_type='application/javascript')

@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def salud(request):
    """Comprobación de vida para el hosting y el monitor externo.

    No basta con que el proceso responda: una app que arranca pero no
    alcanza la base atiende peticiones y las falla todas, y para el hosting
    eso se ve igual que estar sana. Acá se toca la base y la caché de
    verdad, y se devuelve 503 si alguna no contesta, que es lo que hace que
    el reinicio automático sirva de algo.

    Sin autenticación a propósito: el verificador del hosting no tiene
    sesión. No revela nada — solo qué piezas responden.
    """
    from django.db import connection

    partes = {}
    ok = True

    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        partes['base'] = 'ok'
    except Exception as e:
        partes['base'] = 'error'
        ok = False
        logger.error('Health check: la base no responde (%s)', type(e).__name__)

    try:
        from django.core.cache import cache
        cache.set('salud', '1', 10)
        partes['cache'] = 'ok' if cache.get('salud') == '1' else 'error'
        if partes['cache'] == 'error':
            ok = False
    except Exception as e:
        partes['cache'] = 'error'
        ok = False
        logger.error('Health check: la caché no responde (%s)', type(e).__name__)

    return JsonResponse({'estado': 'ok' if ok else 'degradado', 'partes': partes},
                        status=200 if ok else 503)

