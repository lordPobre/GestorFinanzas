from django.db import migrations
from django.db.models import Q

LOTE = 1000


def completar(apps, schema_editor):
    Transaccion = apps.get_model('finanzas', 'Transaccion')
    sin_marcar = Transaccion.objects.filter(origen='manual')

    sin_marcar.filter(pago_cuota__isnull=False).update(origen='cuota')
    sin_marcar.filter(
        Q(gasto_pendiente__isnull=False)
        | Q(tipo='EGRESO', es_cuota=False, descripcion__startswith='Pendiente: ')
    ).update(origen='pendiente')
    sin_marcar.filter(
        Q(suscripcion__isnull=False)
        | Q(tipo='EGRESO', es_cuota=False, descripcion__startswith='Suscripción: ')
    ).update(origen='suscripcion')

    vistos, cambios = set(), []
    cobros = (Transaccion.objects.filter(suscripcion__isnull=False)
              .order_by('suscripcion_id', 'fecha', 'id')
              .only('id', 'suscripcion_id', 'fecha'))
    for t in cobros.iterator(chunk_size=2000):
        clave = (t.suscripcion_id, t.fecha.year * 100 + t.fecha.month)
        if clave in vistos:
            continue
        vistos.add(clave)
        t.periodo_cobro = clave[1]
        cambios.append(t)
        if len(cambios) >= LOTE:
            Transaccion.objects.bulk_update(cambios, ['periodo_cobro'])
            cambios = []
    if cambios:
        Transaccion.objects.bulk_update(cambios, ['periodo_cobro'])


def deshacer(apps, schema_editor):
    apps.get_model('finanzas', 'Transaccion').objects.update(origen='manual', periodo_cobro=None)


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0128_transaccion_origen_periodo'),
    ]

    operations = [
        migrations.RunPython(completar, deshacer),
    ]
