from django.db import migrations
from django.db.models import Exists, F, OuterRef, Q, Subquery

MODELOS = ('Transaccion', 'TopeCategoria', 'GastoPendiente', 'Suscripcion', 'Deuda')
RESPALDO = {'Transaccion': 'Otros', 'GastoPendiente': 'Cuentas', 'Suscripcion': 'Suscripciones',
            'Deuda': 'Otros'}


def completar(apps, schema_editor):
    from finanzas.categorias_base import BASE

    Categoria = apps.get_model('finanzas', 'Categoria')
    for slug, nombre, tipo, color, icono in BASE:
        Categoria.objects.get_or_create(
            usuario=None, slug=slug,
            defaults={'nombre': nombre, 'tipo': tipo, 'color': color, 'icono': icono, 'activa': True})
    base = dict(Categoria.objects.filter(usuario__isnull=True).values_list('slug', 'id'))

    for nombre in MODELOS:
        modelo = apps.get_model('finanzas', nombre)
        modelo.objects.filter(categoria_ref__isnull=False).filter(
            ~Q(categoria_ref__slug=F('categoria'))
            | (Q(categoria_ref__usuario__isnull=False) & ~Q(categoria_ref__usuario=F('usuario')))
        ).update(categoria_ref_id=None)

        for filtro in ({'usuario_id': OuterRef('usuario_id')}, {'usuario__isnull': True}):
            cat = Categoria.objects.filter(slug=OuterRef('categoria'), **filtro)
            (modelo.objects.filter(categoria_ref__isnull=True).filter(Exists(cat))
             .update(categoria_ref_id=Subquery(cat.values('id')[:1])))

        sueltos = modelo.objects.filter(categoria_ref__isnull=True)
        if nombre == 'TopeCategoria':
            sueltos.delete()
            continue
        if nombre == 'Transaccion':
            sueltos.filter(tipo='INGRESO').update(
                categoria='Otros_Ingresos', categoria_ref_id=base['Otros_Ingresos'])
        slug = RESPALDO[nombre]
        sueltos.update(categoria=slug, categoria_ref_id=base[slug])


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0131_categoria_sin_choices'),
    ]

    operations = [
        migrations.RunPython(completar, migrations.RunPython.noop),
    ]
