import calendar
import csv
import json
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from dateutil.relativedelta import relativedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.db.models import Count, F, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from .forms import DeudaForm, MetaAhorroForm, TransaccionForm
from .seguridad import (MAX_INTENTOS as MAX_INTENTOS_LOGIN, _ip, esta_bloqueado,
                        limitar, limpiar_intentos, registrar_fallo)
from .models import (AbonoPrestamo, AporteMeta, Categoria, CodigoRespaldo, Deuda, GastoPendiente,
                     MetaAhorro, PagoCuota, PagoServicio, Persona, Prestamo,
                     Presupuesto, SegundoFactor, Suscripcion, Transaccion,
                     UserProfile)

NOMBRES_MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

MESES_LARGOS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
                'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def nombre_mes_es(year, month, capitalizado=True):
    """Mes en español.

    strftime('%B') usa el locale del SISTEMA, no LANGUAGE_CODE de Django, así
    que en el servidor devolvía 'August' aunque la app esté en español.
    """
    texto = f'{MESES_LARGOS[month - 1]} {year}'
    return texto.capitalize() if capitalizado else texto


# ============================================================
#  HELPERS
# ============================================================

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

    # Solo la cadena de consulta: se completa con la ruta de la que vino.
    if destino.startswith('?'):
        base = request.POST.get('next_path') or request.path
        # request.path es la URL de la ACCIÓN (por ejemplo
        # /suscripciones/pagar/4/), no la de la pantalla. Si no viene un
        # next_path explícito se cae a la pantalla por defecto con la
        # consulta pegada, que es lo único razonable.
        if base == request.path:
            base = reverse(por_defecto)
        return redirect(f'{base}{destino}')

    # Ruta interna.
    if destino.startswith('/') and not destino.startswith('//'):
        return redirect(destino)

    # Nombre de ruta. Si no existe, no se rompe la acción por un 'next' malo.
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

    # Gastos del día a día. Excluye los pagos de cuotas (es_cuota=True)
    # porque las cuotas del mes se suman aparte, completas.
    qs_gastos = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO',
        fecha__gte=fecha_inicio, fecha__lte=fecha_fin, es_cuota=False,
    )
    gastos = float(qs_gastos.aggregate(t=Sum('monto'))['t'] or 0)

    # Del total gastado, cuánto salió de verdad y cuánto sigue debiéndose.
    # Los dos cuentan como gasto del mes: la diferencia es si la plata ya
    # se fue o si todavía la tienes en el bolsillo.
    gastos_pagados = float(qs_gastos.filter(pagado=True)
                                    .aggregate(t=Sum('monto'))['t'] or 0)
    gastos_por_pagar = gastos - gastos_pagados

    # El periodo es la clave con la que se guardan los pagos: año*100+mes.
    periodo = year * 100 + month

    deudas = Deuda.objects.filter(usuario=usuario).prefetch_related('pagos')
    cuotas_pagadas = 0.0
    cuotas_pendientes = 0.0
    eventos = {}

    for d in deudas:
        # ¿Esta compra cobra en este mes? Se pregunta al calendario de la
        # deuda, no a una resta de fechas suelta.
        if periodo not in d.periodos_programados:
            continue

        fecha_cobro = d.fecha_cobro_de(periodo)
        dia_venc = fecha_cobro.day

        # El estado sale de si EXISTE un pago para este mes.
        #
        # Antes se deducía: los meses pasados se daban por pagados sin mirar
        # nada, y el mes en curso se comparaba contra un contador. Un mes
        # impago se veía limpio al navegar atrás, y quien se adelantaba
        # dejaba meses futuros marcados como pagados.
        pago = next((p for p in d.pagos.all() if p.periodo == periodo), None)
        estado = 'pagado' if pago else 'pendiente'

        # El monto es el de la cuota de ESE mes: la última absorbe el residuo
        # del redondeo, así la suma de las cuotas da el total exacto.
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

    # Suscripciones del mes.
    #
    # El cobro ya está dentro de 'gastos' (generar_cobros_suscripciones crea
    # la transacción en cuanto llega el mes), así que NO se suma otra vez.
    # Lo que se calcula acá es solo el reparto: cuánto de ese gasto ya salió
    # del bolsillo y cuánto sigue pendiente.
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
        'gastos_pagados': gastos_pagados,
        'gastos_por_pagar': gastos_por_pagar,
        'cuotas_pagadas_mes': cuotas_pagadas,
        'cuotas_pendientes_mes': cuotas_pendientes,
        'total_cuotas_mes': total_cuotas,
        'servicios_pagados_mes': servicios_pagados,
        'servicios_pendientes_mes': servicios_pendientes,
        'total_servicios_mes': servicios_pagados + servicios_pendientes,
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

    # La nota explica el punto más débil, no repite el número.
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

    # Los pagos se indexan una vez por deuda: recorrer pagos dentro del bucle
    # de meses haría una consulta por mes.
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

        # Lo que aún se deberá al terminar ese mes: solo cuenta los periodos
        # sin pago, así el saldo baja al pagar y no por el paso del tiempo.
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
            'url_pagar': f'/suscripciones/pagar/{s.pk}/',
            'url_anular': f'/suscripciones/anular-pago/{s.pk}/',
            'periodo': periodo,
        })

    # Gastos únicos anotados pero sin pagar. Son los del bloque "ya gastaste".
    #
    # Se excluyen los cobros que genera una suscripción: ya entran arriba
    # desde el propio modelo Suscripcion, y contarlos también acá duplicaba
    # cada servicio en la lista Y en el total del mes.
    #
    # Igual con los gastos pendientes: su transacción se crea al registrarlos
    # y el bloque de abajo los añade desde GastoPendiente.
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
    # Lo atrasado primero, después por fecha; lo pagado al final.
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
    # 'personas' ya trae los préstamos con sus abonos: la tarjeta "Te deben"
    # del dashboard usaba esto mismo pero con una consulta propia y aparte.
    # Se calcula una sola vez, acá, y el dashboard lo toma de este contexto.
    total_por_cobrar = round(sum(p.total_pendiente for p in personas))
    hoy = date.today()
    datos = {
        'cuotas_activas': cuotas_activas,
        'prestamos_activos': prestamos_activos,
        'total_por_cobrar': total_por_cobrar,

        # El perfil del saludo. El encabezado con el avatar y el nombre vive
        # en base.html, así que lo necesitan las nueve pantallas: sin esto el
        # avatar mostraba "?" y el nombre caía al username en todas menos
        # Inicio y Perfil, que eran las dos que lo pasaban a mano.
        'profile': get_or_create_profile(usuario),

        # El panel de registro vive en base.html, así que estas listas hacen
        # falta en TODAS las pantallas. Antes solo las ponía el dashboard y
        # en el resto el panel se abría sin categorías.
        # Panel de registro.
        #
        # Se llama 'form_registro', NO 'form': contadores() se aplica con
        # context.update() al final de cada vista, así que un 'form' acá
        # pisaba el formulario propio de la pantalla (en Cuotas borraba el
        # DeudaForm y el modal salía sin campos).
        'form_registro': TransaccionForm(initial={'tipo': 'EGRESO', 'fecha': hoy}),
        'hoy_iso': hoy.isoformat(),
        # Las de gasto se pintan en el HTML (el tipo por defecto), así que la
        # lista tiene que existir también sin pasar por JSON. Antes solo
        # estaban las versiones JSON y el panel arrancaba sin categorías
        # hasta que corría el script.
        #
        # Incluyen las categorías propias del usuario: si alguien creó
        # "Mascotas" y no aparece acá, la pantalla de Categorías queda de
        # adorno.
        'cats_egreso': Categoria.opciones(usuario, 'EGRESO'),
        'cats_ingreso': Categoria.opciones(usuario, 'INGRESO'),
        # Listas, no cadenas: json_script serializa por su cuenta y escapa
        # los caracteres que podrían cerrar la etiqueta <script>. Antes se
        # llamaba a Categoria.opciones() cuatro veces en total en esta
        # función (dos de ellas pisadas por estas mismas líneas, sin usarse
        # nunca): ahora se llama dos veces, una por lista.
        'cats_egreso_json': [list(c) for c in Categoria.opciones(usuario, 'EGRESO')],
        'cats_ingreso_json': [list(c) for c in Categoria.opciones(usuario, 'INGRESO')],

        # Suscripciones sin pagar este mes: el badge del menú
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
            # El cobro se genera porque llegó el mes, no porque se pagó.
            # Nace sin pagar y se marca desde la pantalla de suscripciones.
            # Los meses anteriores al actual se dan por pagados: si el
            # servicio siguió activo, es porque se pagó.
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

        # Antes se guardaba siempre, incluso sin cambios: un UPDATE por
        # suscripción en cada carga del dashboard.
        if genero_algo:
            sub.save(update_fields=['ultimo_mes_generado'])


# ============================================================
#  DASHBOARD
# ============================================================
#
# Cada función de abajo era un bloque suelto dentro de dashboard(): calendario,
# serie de 6 meses, categorías, deuda por compra, proyecciones e insights.
# Separadas, cada una se puede leer y testear sin montar un request completo,
# y dashboard() queda como la lista de qué se calcula, no el cómo.

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
    # Lo atrasado primero; después lo que más falta por pagar.
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


# Cómo se pinta cada tipo de aviso: color del icono, fondo de su ficha,
# borde de la tarjeta y la palabra que la encabeza.
#
# Vive acá y no en la plantilla porque allá obligaba a repetir el mismo
# bloque de marcado cuatro veces, una por tipo, con la única diferencia de
# los colores.
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

    # El color y la etiqueta de cada aviso, resueltos de una vez.
    for i in insights:
        i.update(TONOS_INSIGHT.get(i['tipo'], TONOS_INSIGHT['info']))

    return insights, presupuesto_pct


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

    # ---------- Próximo pago ----------
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
    # Lo que se libera cuando termine la deuda más próxima
    se_libera = proyecciones_deuda[0] if proyecciones_deuda else None

    context = {
        'nombre_mes': nombre_mes,
        'es_nuevo': es_nuevo,
        'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year,
        'year': year, 'month': month,
        'es_mes_actual': (year, month) == (hoy.year, hoy.month),
        # Para que las flechas digan a qué mes llevan, no solo "anterior"
        'prev_month_nombre': nombre_mes_es(prev_year, prev_month),
        'next_month_nombre': nombre_mes_es(next_year, next_month),
        'dias_semana': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],

        # Números del mes
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
        'deuda_total': round(deuda_total),

        # Deuda en cuotas, vista completa
        'mis_cuotas': mis_cuotas,
        'deuda_bruta_total': deuda_bruta_total,
        'deuda_pagada_total': deuda_pagada_total,
        'deuda_pct_pagado': (round(deuda_pagada_total / deuda_bruta_total * 100)
                             if deuda_bruta_total else 0),
        'cuota_mensual_total': round(sum(c['cuota'] for c in mis_cuotas)),
        'cuotas_atrasadas_total': sum(c['atrasadas'] for c in mis_cuotas),

        # Gasto mensual comprometido: cuotas + suscripciones activas.
        # Es lo que sale todos los meses pase lo que pase, y no estaba a la
        # vista en ninguna parte.
        'fijo_mensual': round(
            sum(c['cuota'] for c in mis_cuotas)
            + sum(float(s.monto) for s in Suscripcion.objects.filter(
                usuario=request.user, activa=True))
        ),

        # Nuevos: los usa el encabezado "Puedes gastar X hasta fin de mes".
        # por_pagar suma cuotas y servicios sin pagar. No se resta aparte del
        # disponible: los servicios ya están contados dentro de los gastos.
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

        # Formulario del panel de registro, para no salir del dashboard
        # El form, hoy_iso y las categorías del panel los entrega contadores(),
        # porque el panel ahora está en base.html y lo usan todas las pantallas.
        'abrir_panel': bool(request.GET.get('registrar')),

        'meses_json': meses_labels,
        'ingresos_json': datos_ingresos,
        'gastos_json': datos_gastos,
        'cuotas_json': datos_cuotas,
        'cat_labels_json': [c['label'] for c in categorias],
        'cat_data_json': [c['total'] for c in categorias],
        'cat_colores_json': [c['color'] for c in categorias],
    }
    # La tarjeta "Te deben" del carrusel: total_por_cobrar lo entrega
    # contadores() más abajo (context.update), que ya consulta Persona con
    # sus préstamos para el badge del menú. Antes esta vista repetía esa
    # misma consulta aparte, solo para sacar la suma.

    # La fecha larga bajo "Puedes gastar", como en la plantilla.
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    context['hoy_texto'] = (f'{dias_semana[hoy.weekday()]}, {hoy.day} '
                            f'{MESES_LARGOS[hoy.month - 1]} {hoy.year}')

    # La variación del saldo contra el mes anterior: es el dato que da
    # sentido al gráfico ("vas mejor o peor que el mes pasado").
    f_ant = date(year, month, 1) - relativedelta(months=1)
    r_ant = resumen_mes(request.user, f_ant.year, f_ant.month)
    saldo_ant = r_ant['disponible']
    if saldo_ant:
        var_saldo = round((r['disponible'] - saldo_ant) / abs(saldo_ant) * 100)
        context['variacion_saldo'] = var_saldo
        context['variacion_saldo_abs'] = abs(var_saldo)
    else:
        # Sin mes anterior con datos no hay con qué comparar; el template
        # esconde la píldora en vez de mostrar un 0% que no significa nada.
        context['variacion_saldo'] = None
        context['variacion_saldo_abs'] = None
    context['mes_anterior_nombre'] = MESES_LARGOS[f_ant.month - 1]

    context['mapa_categorias'] = Categoria.mapa(request.user)
    # Si se está viendo el mes en curso, 'r' YA es el resumen que
    # salud_financiera() necesita: contadores() lo reusa en vez de volver a
    # consultar Transaccion/Deuda/Suscripcion para el mismo mes.
    context.update(contadores(
        request.user,
        resumen_actual=r if (year, month) == (hoy.year, hoy.month) else None,
    ))
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
    lista = list(Deuda.objects.filter(usuario=request.user).prefetch_related('pagos'))
    activas = [d for d in lista if not d.esta_saldada]

    # Orden: primero lo atrasado, después lo que vence antes.
    activas.sort(key=lambda d: (
        -len(d.periodos_atrasados),
        d.dias_para_vencer if d.dias_para_vencer is not None else 9999,
    ))
    saldadas = [d for d in lista if d.esta_saldada]

    proximas = [d for d in activas if d.dias_para_vencer is not None]
    proximas.sort(key=lambda d: d.fecha_fin_estimada)

    context = {
        'deudas': activas,
        # El histórico, aparte. Lo más reciente primero: al terminar de pagar
        # algo se busca eso, no la compra de hace dos años.
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

    # Qué mes se paga: el pedido, o el pendiente más antiguo.
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

    # El gasto se fecha en el mes al que pertenece la cuota, no en el día en
    # que se apretó el botón. Antes, pagar en marzo la cuota de enero dejaba
    # el movimiento en marzo y la cuota de enero no se contaba en ningún mes.
    tx = Transaccion.objects.create(
        usuario=request.user, tipo='EGRESO', monto=monto,
        categoria=deuda.categoria,
        descripcion=f'Cuota {numero}/{deuda.cuotas_totales} — {deuda.acreedor}',
        fecha=fecha_cobro, es_cuota=True,
        # Nace pagada: la transacción se crea justamente porque se pagó.
        pagado=True, fecha_pago=hoy,
    )
    PagoCuota.objects.create(
        deuda=deuda, periodo=periodo, monto=monto, fecha_pago=hoy, transaccion=tx,
    )

    # cuotas_pagadas queda como espejo del recuento real, para que el resto
    # del código y las plantillas antiguas sigan funcionando.
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

    # Sin periodo se anula el pago más reciente.
    pago = (deuda.pagos.filter(periodo=periodo).first() if periodo
            else deuda.pagos.order_by('-periodo').first())

    if not pago:
        if es_ajax:
            return JsonResponse({'ok': False, 'msg': 'No hay pagos que anular.'})
        messages.warning(request, 'No hay pagos que anular.')
        return _redirigir(request)

    etiqueta = pago.etiqueta_mes
    if pago.transaccion:
        pago.transaccion.delete()   # el pago cae con ella (SET_NULL + delete abajo)
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


# ============================================================
#  TRANSACCIONES
# ============================================================

@login_required(login_url='/login/')
def registrar_transaccion(request):
    tipo_inicial = request.GET.get('tipo', 'INGRESO')
    if request.method == 'POST':
        form = TransaccionForm(request.POST, usuario=request.user)
        if form.is_valid():
            t = form.save(commit=False)
            t.usuario = request.user
            # El panel manda 'sin_pagar' cuando el gasto se anota pero no se
            # ha pagado todavía.
            # Dos plantillas mandan esto con nombres distintos: el panel del
            # dashboard usa 'sin_pagar' y el formulario completo 'es_pendiente'.
            # Antes solo se leía uno y el checkbox del formulario no hacía nada.
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

        # Antes esto caía en form_transaccion.html y el usuario no veía por qué
        # había fallado. Ahora el error se muestra y, si vino del panel del
        # dashboard, se vuelve ahí con el panel abierto.
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


# ============================================================
#  ESTADÍSTICAS
# ============================================================

@login_required(login_url='/login/')
def estadisticas(request):
    hoy = date.today()
    # prefetch_related('pagos'): sin esto, monto_restante y monto_cuota más
    # abajo abren una consulta de pagos POR CADA deuda activa (N+1) — con
    # 5 deudas son 5 consultas extra en cada carga de Estadísticas.
    activas = [d for d in Deuda.objects.filter(usuario=request.user)
                                        .prefetch_related('pagos') if not d.esta_saldada]

    labels = [d.acreedor for d in activas]
    data_cuota = [float(d.monto_cuota) for d in activas]
    data_restante = [float(d.monto_restante) for d in activas]

    # Serie de 12 meses para el gráfico de rango, y el ranking de categorías.
    # El mes en curso (i=0, el último de la vuelta) se guarda: es el mismo
    # que contadores() necesita para salud_financiera(), y sin esto se
    # volvía a calcular una 13ª vez al final de la vista.
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

    # Seis meses atrás y seis adelante, con las cuotas ya pagadas incluidas.
    serie = serie_cuotas(request.user, atras=6, adelante=6)
    indice_actual = next((i for i, f in enumerate(serie) if f['es_mes_actual']), 0)

    context = {
        'analisis': analisis,
        'simbolo': _simbolo_moneda(request.user),
        'riesgo_offset': round(riesgo_offset, 1),
        'serie': serie,
        # Cuotas que ya vencieron y no se pagaron: plata que se debe hoy,
        # no una proyección. Antes no aparecía en el análisis.
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

        # Nace sin pagar: es justamente una cuenta que falta pagar. Antes
        # entraba como pagada y "ya gastaste" contaba plata que no había
        # salido del bolsillo.
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
        # La transacción asociada también queda pagada, si no el gasto
        # seguiría apareciendo como pendiente en "ya gastaste".
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


# ============================================================
#  SUSCRIPCIONES
# ============================================================

@login_required(login_url='/login/')
def suscripciones(request):
    """Lista de suscripciones (activas e inactivas)."""
    subs = list(Suscripcion.objects.filter(usuario=request.user).prefetch_related('pagos'))
    activas = [s for s in subs if s.activa]
    total_mensual = sum(float(s.monto) for s in activas)

    # Orden: lo que falta pagar primero, después lo del mes, al final las pausadas.
    orden = {'atrasada': 0, 'pendiente': 1, 'pagada': 2, 'pausada': 3}
    subs.sort(key=lambda s: (orden.get(s.estado_mes, 9), s.nombre))

    pendientes = [s for s in activas if not s.pagada_este_mes]
    atrasadas = [s for s in activas if s.periodos_atrasados]

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
    # La transacción de ese mes también queda pagada, para que el reparto de
    # "ya gastaste" cuadre con lo que marcaste acá.
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
#  CATEGORÍAS
# ============================================================

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
    # Cuántos movimientos tiene cada una: decide si se puede borrar sin
    # dejar movimientos huérfanos.
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

    # Lo más usado arriba: es lo que el usuario quiere revisar.
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


# ============================================================
#  METAS DE AHORRO
# ============================================================

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

    # Los seis meses del gráfico, con los aportes de cada meta por mes.
    meses = []
    for i in range(5, -1, -1):
        f = date(hoy.year, hoy.month, 1) - relativedelta(months=i)
        meses.append({'clave': f.year * 100 + f.month,
                      'label': NOMBRES_MESES[f.month - 1]})

    datos = []
    for meta in lista:
        # 'aportes' ya viene prefetcheado (una sola consulta para TODAS las
        # metas, arriba en el queryset de 'lista') y ordenado por -fecha,
        # -id, que es el ordering por defecto de AporteMeta. Antes se leía
        # con meta.aportes.all() para la serie Y con meta.aportes.first()
        # para el último aporte: ese .first() abre un queryset nuevo con
        # LIMIT 1 que ignora el cache del prefetch, así que cada meta hacía
        # una consulta extra a la base — cinco metas, cinco consultas de
        # más solo para saber la fecha del último aporte.
        aportes = list(meta.aportes.all())
        por_mes = {}
        for ap in aportes:
            k = ap.fecha.year * 100 + ap.fecha.month
            por_mes[k] = por_mes.get(k, 0) + float(ap.monto)

        serie = [por_mes.get(m['clave'], 0) for m in meses]
        techo = max(serie) or 1
        # El último aporte dice si la meta sigue viva. Ya está ordenado
        # primero-el-más-reciente, así que es el primer elemento de la lista.
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

    # Las completas al final: ya no hay nada que hacer con ellas.
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


# ============================================================
#  REGISTRO Y ONBOARDING
# ============================================================

def entrar(request):
    """Acceso con tope de intentos.

    La LoginView de Django no limita nada: se pueden probar contraseñas sin
    fin. En una app con datos financieros eso es la puerta más fácil, así
    que cinco fallos bloquean quince minutos.
    """
    from django.contrib.auth import authenticate
    from django.contrib.auth.forms import AuthenticationForm

    ip = _ip(request)
    usuario_txt = (request.POST.get('username') or '').strip()[:150]
    restan = esta_bloqueado(usuario_txt, ip)

    if request.method == 'POST' and restan:
        minutos = max(1, restan // 60)
        messages.error(
            request,
            f'Demasiados intentos fallidos. Espera {minutos} minuto'
            + ('s' if minutos != 1 else '') + ' antes de volver a probar.')
        return render(request, 'registration/login.html',
                      {'form': AuthenticationForm(), 'bloqueado': True})

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            usuario = form.get_user()
            limpiar_intentos(usuario_txt, ip)

            # Con 2FA activo la contraseña sola no entra: se guarda en la
            # sesión QUIÉN está a medio autenticar y se pide el código.
            #
            # No se llama a login() todavía. Si se llamara, la sesión ya
            # estaría abierta y bastaría con navegar a cualquier URL para
            # saltarse el segundo paso.
            factor = SegundoFactor.objects.filter(usuario=usuario, activo=True).first()
            if factor:
                request.session['2fa_pendiente'] = usuario.pk
                request.session['2fa_next'] = request.POST.get('next', '')
                return redirect('verificar_codigo')

            login(request, usuario)
            destino = request.POST.get('next') or request.GET.get('next')
            # Solo rutas internas: un 'next' externo es una redirección
            # abierta, útil para phishing con un enlace de tu propio dominio.
            if destino and destino.startswith('/') and not destino.startswith('//'):
                return redirect(destino)
            return redirect('dashboard')

        intentos = registrar_fallo(usuario_txt, ip)
        quedan = MAX_INTENTOS_LOGIN - intentos
        # El mensaje no dice si el usuario existe: eso permitiría averiguar
        # qué cuentas hay probando nombres.
        if quedan > 0:
            messages.error(
                request,
                'Usuario o contraseña incorrectos. '
                f'Te queda{"n" if quedan != 1 else ""} {quedan} intento'
                + ('s' if quedan != 1 else '') + '.')
        else:
            messages.error(request, 'Demasiados intentos. Espera 15 minutos.')
        return render(request, 'registration/login.html', {'form': form})

    return render(request, 'registration/login.html',
                  {'form': AuthenticationForm()})


def verificar_codigo(request):
    """Segundo paso del acceso.

    El usuario llega con '2fa_pendiente' en la sesión, puesto por entrar().
    Hasta que el código sea correcto no hay login(), así que no puede tocar
    ninguna pantalla de la app.
    """
    uid = request.session.get('2fa_pendiente')
    if not uid:
        return redirect('login')

    try:
        usuario = User.objects.get(pk=uid)
        factor = usuario.segundo_factor
    except (User.DoesNotExist, SegundoFactor.DoesNotExist):
        request.session.pop('2fa_pendiente', None)
        return redirect('login')

    ip = _ip(request)
    clave_2fa = f'2fa:{uid}'

    if request.method == 'POST':
        # El código también se limita: seis dígitos son un millón de
        # combinaciones, y sin tope se prueban todas en minutos.
        restan = esta_bloqueado(clave_2fa, ip)
        if restan:
            messages.error(request, f'Demasiados intentos. Espera {max(1, restan // 60)} minutos.')
            return render(request, 'registration/verificar.html', {'bloqueado': True})

        codigo = request.POST.get('codigo', '')
        usa_respaldo = bool(request.POST.get('es_respaldo'))

        ok = (CodigoRespaldo.consumir(usuario, codigo) if usa_respaldo
              else factor.verificar(codigo))

        if ok:
            limpiar_intentos(clave_2fa, ip)
            request.session.pop('2fa_pendiente', None)
            destino = request.session.pop('2fa_next', '')
            login(request, usuario)

            if usa_respaldo:
                quedan = CodigoRespaldo.objects.filter(usuario=usuario, usado=False).count()
                messages.warning(
                    request,
                    f'Usaste un código de respaldo. Te quedan {quedan}. '
                    'Genera otros desde tu perfil si te quedan pocos.')

            if destino and destino.startswith('/') and not destino.startswith('//'):
                return redirect(destino)
            return redirect('dashboard')

        registrar_fallo(clave_2fa, ip)
        messages.error(request, 'Código incorrecto o ya usado.')

    return render(request, 'registration/verificar.html', {
        'usuario': usuario,
        'tiene_respaldo': CodigoRespaldo.objects.filter(usuario=usuario, usado=False).exists(),
    })


def _qr_svg(uri, escala=6):
    """Código QR como SVG, listo para incrustar en el HTML.

    SVG y no PNG: escala sin pixelarse y no necesita Pillow ni guardar un
    archivo. Se dibuja como una sola ruta de rectángulos, que pesa poco.

    Si la librería no está instalada devuelve None y la pantalla muestra la
    clave manual, que funciona igual de bien aunque sea más incómoda.
    """
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(
        version=None,
        # Corrección media: el QR sigue leyéndose con el reflejo de la
        # pantalla o con la cámara algo movida.
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1, border=2,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    matriz = qr.get_matrix()

    lado = len(matriz) * escala
    piezas = []
    for y, fila in enumerate(matriz):
        x = 0
        while x < len(fila):
            if fila[x]:
                # Se agrupan los módulos negros seguidos en un solo
                # rectángulo: un <rect> por módulo daría un SVG cinco veces
                # más grande.
                ancho = 1
                while x + ancho < len(fila) and fila[x + ancho]:
                    ancho += 1
                piezas.append(
                    f'M{x * escala} {y * escala}h{ancho * escala}v{escala}h-{ancho * escala}z')
                x += ancho
            else:
                x += 1

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" height="{lado}" '
        f'viewBox="0 0 {lado} {lado}" shape-rendering="crispEdges" role="img" '
        f'aria-label="Código QR para configurar la verificación en dos pasos">'
        f'<rect width="{lado}" height="{lado}" fill="#ffffff"/>'
        f'<path d="{"".join(piezas)}" fill="#191919"/>'
        f'</svg>'
    )


@login_required(login_url='/login/')
def configurar_2fa(request):
    """Activar la verificación en dos pasos.

    El secreto se crea al abrir la pantalla pero el factor queda inactivo
    hasta que el usuario confirme un código. Así se comprueba que su app
    quedó bien configurada ANTES de exigirle el código para entrar — si no,
    se quedaría fuera de su propia cuenta.
    """
    factor, _ = SegundoFactor.objects.get_or_create(
        usuario=request.user,
        defaults={'secreto': SegundoFactor.generar_secreto()},
    )

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'activar':
            if factor.verificar(request.POST.get('codigo', '')):
                factor.activo = True
                factor.save(update_fields=['activo'])
                codigos = CodigoRespaldo.generar(request.user)
                messages.success(request, 'Verificación en dos pasos activada.')
                return render(request, 'finanzas/codigos_respaldo.html',
                              {'codigos': codigos, 'recien_creados': True})
            messages.error(request, 'El código no coincide. Revisa la hora de tu teléfono.')

        elif accion == 'desactivar':
            # Se pide la contraseña: si alguien deja la sesión abierta, no
            # debería poder quitar la protección sin conocerla.
            if not request.user.check_password(request.POST.get('password', '')):
                messages.error(request, 'Contraseña incorrecta.')
                return redirect('configurar_2fa')
            factor.delete()
            CodigoRespaldo.objects.filter(usuario=request.user).delete()
            messages.success(request, 'Verificación en dos pasos desactivada.')
            return redirect('perfil')

        elif accion == 'regenerar':
            if not request.user.check_password(request.POST.get('password', '')):
                messages.error(request, 'Contraseña incorrecta.')
                return redirect('configurar_2fa')
            codigos = CodigoRespaldo.generar(request.user)
            return render(request, 'finanzas/codigos_respaldo.html',
                          {'codigos': codigos, 'recien_creados': False})

    # Si aún no está activo se muestra el secreto para configurar la app.
    # Una vez activo ya no: no hay razón para volver a exponerlo.
    contexto = {
        'factor': factor,
        'codigos_restantes': CodigoRespaldo.objects.filter(
            usuario=request.user, usado=False).count(),
    }
    if not factor.activo:
        contexto['uri'] = factor.uri()
        contexto['secreto'] = factor.secreto
        contexto['qr_svg'] = _qr_svg(factor.uri())
        # El secreto en grupos de cuatro: escribirlo a mano de un tirón de 32
        # caracteres es donde la gente se equivoca.
        s = factor.secreto
        contexto['secreto_legible'] = ' '.join(s[i:i + 4] for i in range(0, len(s), 4))
    contexto.update(contadores(request.user))
    return render(request, 'finanzas/configurar_2fa.html', contexto)


# ============================================================
#  RECUPERAR CONTRASEÑA
# ============================================================
#
# Flujo: pides el enlace con tu email → llega un enlace firmado que vale una
# hora → abres el enlace y eliges contraseña nueva. Si tienes verificación
# en dos pasos activa, además hay que escribir el código: si no, el correo
# se convertiría en la única llave de la cuenta y bastaría con entrar a tu
# bandeja para tomarla.
#
# El token lo firma Django (default_token_generator). Dos cosas que hace
# solo y que conviene saber: caduca según PASSWORD_RESET_TIMEOUT, y deja de
# valer en cuanto la contraseña cambia — así un enlace ya usado no sirve
# dos veces.

MAX_SOLICITUDES_RESET = 3
VENTANA_RESET = 900  # 15 minutos


def _usuario_por_correo(correo):
    """Busca por User.email y, si no aparece, por UserProfile.email.

    Las cuentas creadas antes de que el email fuera obligatorio guardaban
    el correo solo en el perfil. Sin este segundo intento, esos usuarios no
    podrían recuperar nunca su contraseña.
    """
    correo = (correo or '').strip()
    if not correo:
        return None
    usuario = User.objects.filter(email__iexact=correo, is_active=True).first()
    if usuario:
        return usuario
    perfil = UserProfile.objects.filter(email__iexact=correo,
                                        usuario__is_active=True).first()
    return perfil.usuario if perfil else None


def recuperar(request):
    """Pide el correo y manda el enlace."""
    from django.contrib.auth.tokens import default_token_generator
    from django.core.cache import cache
    from django.template.loader import render_to_string
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from .correo import configurado as correo_configurado, enviar, url_absoluta

    enviado = False
    correo_txt = ''

    if request.method == 'POST':
        correo_txt = (request.POST.get('email') or '').strip()

        # Tope por IP: sin él, alguien puede usar este formulario para
        # bombardear de correos a una dirección ajena, o para gastar la
        # cuota de envío de la cuenta.
        clave = f'reset:{_ip(request)}'
        usados = cache.get(clave, 0)
        if usados >= MAX_SOLICITUDES_RESET:
            messages.warning(
                request,
                'Ya pediste varios enlaces. Espera unos minutos antes de intentarlo otra vez.')
            return render(request, 'registration/recuperar.html',
                          {'email': correo_txt})
        cache.set(clave, usados + 1, VENTANA_RESET)

        usuario = _usuario_por_correo(correo_txt)
        if usuario:
            enlace = url_absoluta(request, reverse('restablecer', kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(usuario.pk)),
                'token': default_token_generator.make_token(usuario),
            }))
            contexto_correo = {
                'usuario': usuario,
                'enlace': enlace,
                'horas': 1,
            }
            cuerpo = render_to_string('registration/correo_recuperar.txt', contexto_correo)
            cuerpo_html = render_to_string('registration/correo_recuperar.html', contexto_correo)
            if not enviar(usuario.email or correo_txt,
                          'Recupera tu contraseña de FinApp', cuerpo, cuerpo_html):
                # Falla de configuración o de red. Se avisa, porque decir
                # "revisa tu correo" cuando no salió nada es peor.
                logging.getLogger('finanzas').error(
                    'Reset solicitado para %s pero el correo no salió', usuario.pk)
                if not correo_configurado():
                    messages.error(
                        request,
                        'El envío de correos no está configurado todavía. '
                        'Escríbeme y te ayudo a restablecerla a mano.')
                    return render(request, 'registration/recuperar.html',
                                  {'email': correo_txt})
        # Mismo mensaje exista o no la cuenta: si cambiara, este formulario
        # serviría para averiguar qué correos están registrados.
        enviado = True

    return render(request, 'registration/recuperar.html',
                  {'enviado': enviado, 'email': correo_txt})


def restablecer(request, uidb64, token):
    """Valida el enlace y cambia la contraseña."""
    from django.contrib.auth.forms import SetPasswordForm
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        usuario = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        usuario = None

    valido = usuario is not None and default_token_generator.check_token(usuario, token)
    if not valido:
        # No se dice si el enlace es viejo o falso: es la misma respuesta.
        return render(request, 'registration/restablecer.html', {'valido': False})

    factor = SegundoFactor.objects.filter(usuario=usuario, activo=True).first()
    form = SetPasswordForm(usuario)

    if request.method == 'POST':
        form = SetPasswordForm(usuario, request.POST)

        # El segundo factor se comprueba ANTES de guardar: si el código no
        # cuadra, la contraseña no se toca.
        codigo_ok = True
        if factor:
            codigo = (request.POST.get('codigo') or '').strip()
            es_respaldo = request.POST.get('es_respaldo') == '1'
            if es_respaldo:
                codigo_ok = CodigoRespaldo.consumir(usuario, codigo)
            else:
                codigo_ok = factor.verificar(codigo)
            if not codigo_ok:
                form.add_error(None, 'El código de verificación no es correcto.')

        if form.is_valid() and codigo_ok:
            form.save()
            # Los intentos fallidos previos ya no cuentan: la contraseña que
            # se estaba fallando dejó de existir.
            limpiar_intentos(usuario.username, _ip(request))
            messages.success(request, 'Tu contraseña quedó cambiada. Entra con ella.')
            return redirect('login')

    return render(request, 'registration/restablecer.html', {
        'valido': True,
        'form': form,
        'usuario': usuario,
        'pide_codigo': factor is not None,
        'tiene_respaldo': factor is not None and CodigoRespaldo.objects.filter(
            usuario=usuario, usado=False).exists(),
    })


@limitar(5, 3600, 'Demasiados registros desde esta conexión. Prueba más tarde.')
def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        correo = (request.POST.get('email_perfil') or '').strip()
        error_correo = ''

        # El email pasó a ser obligatorio: es la única vía de recuperación
        # de contraseña. Sin él, quien la olvida pierde la cuenta y sus
        # datos, y no hay forma de devolvérsela sin entrar a la base.
        if not correo:
            error_correo = 'Necesitamos tu email para poder recuperar tu contraseña.'
        else:
            try:
                forms.EmailField().clean(correo)
            except forms.ValidationError:
                error_correo = 'Ese email no parece válido. Revísalo.'
            else:
                # Dos cuentas con el mismo correo hacen ambiguo el "olvidé mi
                # contraseña": no se sabría a cuál mandar el enlace.
                if User.objects.filter(email__iexact=correo).exists():
                    error_correo = 'Ya hay una cuenta con ese email.'

        if form.is_valid() and not error_correo:
            user = form.save(commit=False)
            # El correo va también en el User, no solo en el perfil: es donde
            # lo busca la recuperación de contraseña.
            user.email = correo
            user.save()
            login(request, user)
            # get_or_create evita el IntegrityError si ya existe un perfil
            # (por ejemplo si hay una señal post_save que lo crea).
            profile, _ = UserProfile.objects.get_or_create(usuario=user)
            profile.nombre_completo = request.POST.get('nombre_completo', '').strip()
            profile.email = correo
            profile.save()
            return redirect('onboarding')

        if error_correo:
            form.add_error(None, error_correo)
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

    MAX_FOTO_MB = 5
    class Meta:
        model = UserProfile
        fields = ['foto', 'nombre_completo', 'email', 'telefono', 'ciudad', 'pais', 'moneda']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'placeholder': 'Ej: Juan Pérez'}),
            'email':           forms.EmailInput(attrs={'placeholder': 'Ej: juan@email.com'}),
            'telefono':        forms.TextInput(attrs={'placeholder': 'Ej: +56 9 1234 5678'}),
            'ciudad':          forms.TextInput(attrs={'placeholder': 'Ej: Santiago'}),
            'pais':            forms.TextInput(attrs={'placeholder': 'Ej: Chile'}),
            'moneda':          forms.Select(),
            # accept en el propio widget: el selector de archivos del móvil
            # abre directo en la galería en vez de listar todo.
            'foto':            forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_foto(self):
        """Una foto de teléfono pesa 5-12 MB sin comprimir. Sin tope, el
        servidor las guarda todas y el avatar de 40px descarga megas."""
        foto = self.cleaned_data.get('foto')
        if foto and getattr(foto, 'size', 0) > self.MAX_FOTO_MB * 1024 * 1024:
            raise forms.ValidationError(
                f'La imagen pesa demasiado. El máximo son {self.MAX_FOTO_MB} MB.')
        return foto


@login_required(login_url='/login/')
def perfil(request):
    profile = get_or_create_profile(request.user)
    pw_form = PasswordChangeForm(request.user)
    perfil_form = PerfilForm(instance=profile)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'perfil':
            # request.FILES: sin él el archivo subido nunca llega al form y
            # la foto se guardaba siempre vacía.
            perfil_form = PerfilForm(request.POST, request.FILES, instance=profile)
            if perfil_form.is_valid():
                # Volver al avatar de inicial. El save() del modelo borra el
                # archivo del almacenamiento al detectar el cambio.
                if request.POST.get('quitar_foto'):
                    perfil_form.instance.foto = None
                perfil_form.save()
                nombre = perfil_form.cleaned_data.get('nombre_completo', '').strip()
                if nombre:
                    partes = nombre.split(' ', 1)
                    request.user.first_name = partes[0]
                    request.user.last_name = partes[1] if len(partes) > 1 else ''
                    request.user.save(update_fields=['first_name', 'last_name'])
                # El correo se copia al User: es donde lo busca la
                # recuperación de contraseña. Si solo viviera en el perfil,
                # quien lo agregue desde acá seguiría sin poder recuperarla.
                correo = (perfil_form.cleaned_data.get('email') or '').strip()
                if correo and correo.lower() != (request.user.email or '').lower():
                    if not User.objects.filter(email__iexact=correo).exclude(
                            pk=request.user.pk).exists():
                        request.user.email = correo
                        request.user.save(update_fields=['email'])
                    else:
                        messages.warning(
                            request,
                            'Ese email ya está en otra cuenta, así que no se usará '
                            'para recuperar la contraseña de esta.')
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
        'miembro_desde': nombre_mes_es(request.user.date_joined.year,
                                       request.user.date_joined.month),
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
