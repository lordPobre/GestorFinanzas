from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.template.loader import render_to_string

from . import correo
from .models import Deuda, GastoPendiente, Prestamo, Transaccion

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

SIMBOLOS = {'CLP': '$', 'USD': 'US$', 'EUR': '€', 'ARS': '$', 'MXN': '$',
            'COP': '$', 'PEN': 'S/', 'BRL': 'R$'}


def periodo_de(fecha):
    return fecha.year * 100 + fecha.month


def plata(valor, simbolo='$'):
    entero = int(round(float(valor or 0)))
    return f'{simbolo}{entero:,}'.replace(',', '.')


def _dia_mes(fecha):
    return f'{fecha.day} de {MESES[fecha.month - 1]}'


def _cuotas(usuario, hoy, simbolo):
    periodo = periodo_de(hoy)
    filas = []
    for d in Deuda.objects.filter(usuario=usuario).prefetch_related('pagos'):
        if d.esta_saldada:
            continue
        pendientes = [p for p in d.periodos_pendientes if p <= periodo]
        if not pendientes:
            continue
        atrasados = [p for p in pendientes if p < periodo]
        detalle = f'Cuota {d.cuota_actual} de {d.cuotas_totales}'
        if atrasados:
            n = len(atrasados)
            detalle += f' · {n} mes atrasado' if n == 1 else f' · {n} meses atrasados'
        filas.append({
            'nombre': d.acreedor,
            'detalle': detalle,
            'monto': plata(d.monto_cuota * len(pendientes), simbolo),
            'crudo': Decimal(d.monto_cuota) * len(pendientes),
            'atrasado': bool(atrasados),
        })
    return filas


def _sin_pagar_del_mes(usuario, hoy, simbolo):
    movs = Transaccion.objects.filter(
        usuario=usuario, tipo='EGRESO', es_cuota=False, pagado=False,
        fecha__year=hoy.year, fecha__month=hoy.month,
    ).order_by('fecha')

    suscripciones, sueltos = [], []
    for t in movs:
        nombre = t.descripcion or t.get_categoria_display()
        fila = {
            'nombre': nombre,
            'detalle': _dia_mes(t.fecha),
            'monto': plata(t.monto, simbolo),
            'crudo': t.monto,
            'atrasado': t.fecha < hoy,
        }
        if nombre.startswith('Suscripción:'):
            fila['nombre'] = nombre.split(':', 1)[1].strip()
            suscripciones.append(fila)
        else:
            sueltos.append(fila)
    return suscripciones, sueltos


def _gastos_pendientes(usuario, hoy, simbolo):
    _, ultimo = monthrange(hoy.year, hoy.month)
    fin_de_mes = date(hoy.year, hoy.month, ultimo)
    filas = []
    for g in GastoPendiente.objects.filter(
            usuario=usuario, pagado=False, transaccion__isnull=True,
            fecha_vencimiento__lte=fin_de_mes):
        filas.append({
            'nombre': g.nombre,
            'detalle': g.texto_urgencia or _dia_mes(g.fecha_vencimiento),
            'monto': plata(g.monto, simbolo),
            'crudo': g.monto,
            'atrasado': g.fecha_vencimiento < hoy,
        })
    return filas


def _por_cobrar(usuario, simbolo):
    filas = []
    prestamos = (Prestamo.objects.filter(persona__usuario=usuario)
                 .select_related('persona').prefetch_related('abonos'))
    for p in prestamos:
        if p.esta_pagado:
            continue
        filas.append({
            'nombre': p.persona.nombre,
            'detalle': p.descripcion,
            'monto': plata(p.monto_pendiente, simbolo),
        })
    return filas


def resumen(usuario, hoy=None):
    hoy = hoy or date.today()
    perfil = getattr(usuario, 'profile', None)
    simbolo = SIMBOLOS.get(getattr(perfil, 'moneda', 'CLP'), '$')

    cuotas = _cuotas(usuario, hoy, simbolo)
    suscripciones, sueltos = _sin_pagar_del_mes(usuario, hoy, simbolo)
    pendientes = _gastos_pendientes(usuario, hoy, simbolo)

    grupos = [
        {'titulo': 'Cuotas de compras a plazo', 'filas': cuotas},
        {'titulo': 'Suscripciones', 'filas': suscripciones},
        {'titulo': 'Gastos y cuentas', 'filas': sueltos + pendientes},
    ]
    grupos = [g for g in grupos if g['filas']]

    filas = [f for g in grupos for f in g['filas']]
    total = sum((Decimal(str(f['crudo'])) for f in filas), Decimal('0'))
    atrasados = [f for f in filas if f['atrasado']]

    return {
        'grupos': grupos,
        'cantidad': len(filas),
        'atrasados': len(atrasados),
        'total': plata(total, simbolo),
        'por_cobrar': _por_cobrar(usuario, simbolo),
        'mes': MESES[hoy.month - 1],
        'anio': hoy.year,
        'hay_algo': bool(filas),
    }


def destinatario(usuario):
    perfil = getattr(usuario, 'profile', None)
    return (usuario.email or getattr(perfil, 'email', '') or '').strip()


def enviar_a(usuario, hoy=None):
    destino = destinatario(usuario)
    if not destino:
        return False

    datos = resumen(usuario, hoy)
    if not datos['hay_algo']:
        return False

    nombre = (getattr(getattr(usuario, 'profile', None), 'nombre_completo', '')
              or usuario.first_name or usuario.username)
    contexto = dict(datos, nombre=nombre.split(' ')[0])

    n = datos['cantidad']
    asunto = ('Te queda 1 pago este mes' if n == 1
              else f'Te quedan {n} pagos este mes')
    asunto += f" · {datos['total']}"

    texto = render_to_string('finanzas/correo_pagos.txt', contexto)
    html = render_to_string('finanzas/correo_pagos.html', contexto)
    return correo.enviar(destino, asunto, texto, html)
