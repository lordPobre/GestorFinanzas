import calendar
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import migrations


def reparar(apps, schema_editor):
    Deuda = apps.get_model('finanzas', 'Deuda')
    PagoCuota = apps.get_model('finanzas', 'PagoCuota')
    Transaccion = apps.get_model('finanzas', 'Transaccion')

    for deuda in Deuda.objects.all().iterator():
        pagos = PagoCuota.objects.filter(deuda=deuda)
        faltan = min(deuda.cuotas_pagadas, deuda.cuotas_totales) - pagos.count()
        if faltan > 0 and deuda.cuotas_totales > 0:
            cuota = (deuda.monto_total / deuda.cuotas_totales).quantize(Decimal('1'))
            tomados = set(pagos.values_list('periodo', flat=True))
            for i in range(deuda.cuotas_totales):
                if faltan <= 0:
                    break
                mes = deuda.fecha_inicio + relativedelta(months=i)
                periodo = mes.year * 100 + mes.month
                if periodo in tomados:
                    continue
                dia = min(deuda.fecha_inicio.day, calendar.monthrange(mes.year, mes.month)[1])
                fecha = date(mes.year, mes.month, dia)
                candidatos = list(Transaccion.objects.filter(
                    usuario_id=deuda.usuario_id, tipo='EGRESO', es_cuota=True,
                    fecha=fecha, descripcion__startswith=deuda.acreedor,
                    pago_cuota__isnull=True)[:2])
                PagoCuota.objects.create(
                    deuda=deuda, periodo=periodo, monto=cuota, fecha_pago=fecha,
                    transaccion=candidatos[0] if len(candidatos) == 1 else None)
                faltan -= 1
        Deuda.objects.filter(pk=deuda.pk).update(
            cuotas_pagadas=PagoCuota.objects.filter(deuda=deuda).count())


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0116_transaccion_suscripcion'),
    ]

    operations = [
        migrations.RunPython(reparar, migrations.RunPython.noop),
    ]
