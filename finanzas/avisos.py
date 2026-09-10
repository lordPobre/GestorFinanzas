"""Aviso mensual por correo: lo que queda por pagar.

Lo dispara el comando `avisar_pagos` desde una tarea diaria del hosting, no
una vista: el correo tiene que salir el día 20 aunque nadie abra la app ese
día.

Qué entra en el aviso (todo lo del mes en curso que sigue sin pagarse):
  · cuotas de compras a plazo cuyo mes ya llegó, con lo atrasado aparte
  · cobros de suscripciones sin pagar
  · gastos pendientes sueltos (las cuentas que llegan)
y, al final y sin sumar al total, los préstamos que otros te deben.

Un gasto pendiente crea su propia transacción al nacer, así que se lista
desde las transacciones sin pagar; los GastoPendiente que no tienen
transacción se agregan aparte para no contar dos veces lo mismo.

Si no queda nada por pagar, no se manda nada: un correo mensual que a veces
dice "todo al día" se vuelve ruido y se filtra sin leer.
"""
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
    """Clave del mes: año*100+mes. Es la que usan Deuda y PagoCuota."""
    return fecha.year * 100 + fecha.month


def plata(valor, simbolo='$'):
    """Monto con separador de miles y sin decimales, como en la app."""
    entero = int(round(float(valor or 0)))
    return f'{simbolo}{entero:,}'.replace(',', '.')


def _dia_mes(fecha):
    return f'{fecha.day} de {MESES[fecha.month - 1]}'


def _cuotas(usuario, hoy, simbolo):
    """Cuotas cuyo mes ya llegó y nadie pagó. Las de meses futuros no son
    deuda de este mes y no van en el aviso."""
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
    """Los egresos del mes en curso marcados como no pagados, separados en
    suscripciones y gastos sueltos: son dos decisiones distintas."""
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
    """Cuentas por pagar sin movimiento propio. Las que sí lo tienen ya
    salieron en la lista de arriba y se contarían dos veces."""
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
    """Lo que te deben. No suma al total: es plata que entra, no que sale."""
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
    """Lo que va en el correo. Sin envío ni plantillas: así se puede probar
    y también mostrar en pantalla si algún día hace falta."""
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
    """Dónde llega el aviso. El User manda: es el correo con el que se
    recupera la contraseña, así que es el que está verificado en la práctica."""
    perfil = getattr(usuario, 'profile', None)
    return (usuario.email or getattr(perfil, 'email', '') or '').strip()


def enviar_a(usuario, hoy=None):
    """Manda el aviso. Devuelve True solo si el proveedor lo aceptó.

    Devuelve False —sin error— cuando no hay a dónde mandarlo o cuando no
    queda nada por pagar: el comando decide qué anotar en cada caso.
    """
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
