"""Categorías propias para las compras en cuotas.

Solo cambia `choices` y el `default` de Deuda.categoria, más las categorías
nuevas en Transaccion. Ninguna columna cambia de tipo, así que es una
migración liviana.

La parte de datos reasigna las deudas que quedaron en categorías del día a
día: nadie compra el supermercado en 12 cuotas, así que una deuda en
'Comida' o 'Servicios' casi seguro se guardó ahí por falta de una opción
mejor. Se mueven a 'Otros', que es honesto, en vez de adivinar.

Cambia 'dependencies' por tu migración anterior y corre:

    python manage.py migrate
"""
from django.db import migrations, models


CATEGORIAS_CUOTAS = (
    ('Tecnologia', 'Tecnología y electrónica'),
    ('Compras', 'Compras online'),
    ('Ropa', 'Ropa y calzado'),
    ('Hogar', 'Hogar y muebles'),
    ('Ocio', 'Entretenimiento'),
    ('Viajes', 'Viajes y pasajes'),
    ('Educacion', 'Educación y cursos'),
    ('Salud', 'Salud y Farmacia'),
    ('Transporte', 'Transporte'),
    ('Otros', 'Otra cosa'),
)

# Categorías que ya no existen en una compra a plazo.
RETIRADAS = ['Comida', 'Servicios']


def reasignar(apps, schema_editor):
    Deuda = apps.get_model('finanzas', 'Deuda')
    Deuda.objects.filter(categoria__in=RETIRADAS).update(categoria='Otros')


def revertir(apps, schema_editor):
    """No hay marcha atrás real: la categoría original se perdió al
    reasignar. Se deja como no-op para que la migración sea reversible sin
    fingir que recupera algo."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        # ↓ CAMBIA ESTO por tu migración anterior
        ('finanzas', '0102_gasto_pagado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deuda',
            name='categoria',
            field=models.CharField(choices=CATEGORIAS_CUOTAS, default='Tecnologia',
                                   max_length=50),
        ),
        migrations.RunPython(reasignar, revertir),
    ]
