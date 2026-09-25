import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from ..models import Suscripcion, Transaccion


def generar_cobros_suscripciones(usuario):
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
