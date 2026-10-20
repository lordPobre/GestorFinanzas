import calendar
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db import transaction

from .. import fechas
from ..models import PagoServicio, Suscripcion, Transaccion


def generar_cobros_suscripciones(usuario):
    hoy = fechas.hoy()
    mes_actual = hoy.year * 100 + hoy.month
    ids = list(Suscripcion.objects
               .filter(usuario=usuario, activa=True)
               .exclude(ultimo_mes_generado__gte=mes_actual)
               .values_list('pk', flat=True))
    for pk in ids:
        with transaction.atomic():
            sub = Suscripcion.objects.select_for_update().filter(pk=pk, activa=True).first()
            if sub is not None:
                _generar(sub, mes_actual)


def _generar(sub, mes_actual):
    if sub.ultimo_mes_generado >= mes_actual:
        return
    if sub.ultimo_mes_generado == 0:
        cursor = date(sub.fecha_inicio.year, sub.fecha_inicio.month, 1)
    else:
        ultimo = sub.ultimo_mes_generado
        cursor = date(ultimo // 100, ultimo % 100, 1) + relativedelta(months=1)

    genero_algo = False
    while cursor.year * 100 + cursor.month <= mes_actual:
        periodo = cursor.year * 100 + cursor.month
        _, ult_dia = calendar.monthrange(cursor.year, cursor.month)
        fecha = date(cursor.year, cursor.month, min(sub.dia_cobro, ult_dia))
        en_curso = periodo == mes_actual
        Transaccion.objects.get_or_create(
            suscripcion=sub, periodo_cobro=periodo,
            defaults={
                'usuario_id': sub.usuario_id, 'tipo': 'EGRESO', 'monto': sub.monto,
                'categoria': sub.categoria or 'Suscripciones',
                'descripcion': f'Suscripción: {sub.nombre}', 'fecha': fecha,
                'es_cuota': False, 'origen': Transaccion.SUSCRIPCION,
                'pagado': not en_curso, 'fecha_pago': None if en_curso else fecha,
            },
        )
        if not en_curso:
            PagoServicio.objects.get_or_create(
                suscripcion=sub, periodo=periodo,
                defaults={'monto': sub.monto, 'fecha_pago': fecha},
            )
        sub.ultimo_mes_generado = periodo
        cursor = cursor + relativedelta(months=1)
        genero_algo = True

    if genero_algo:
        sub.save(update_fields=['ultimo_mes_generado'])
