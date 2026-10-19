from django.db import migrations
from django.db.models import Exists, OuterRef, Subquery

BASE = (
    ('Comida', 'Comida y Supermercado', 'EGRESO', '#60a5fa', 'fa-cart-shopping'),
    ('Transporte', 'Transporte y Gasolina', 'EGRESO', '#53d258', 'fa-car'),
    ('Servicios', 'Luz, Agua, Internet', 'EGRESO', '#818cf8', 'fa-bolt'),
    ('Ocio', 'Entretenimiento y Salidas', 'EGRESO', '#fbbf24', 'fa-film'),
    ('Salud', 'Salud y Farmacia', 'EGRESO', '#22d3ee', 'fa-kit-medical'),
    ('Tecnologia', 'Tecnología y electrónica', 'EGRESO', '#818cf8', 'fa-laptop'),
    ('Ropa', 'Ropa y calzado', 'EGRESO', '#f472b6', 'fa-shirt'),
    ('Hogar', 'Hogar y muebles', 'EGRESO', '#2dd4bf', 'fa-couch'),
    ('Viajes', 'Viajes y pasajes', 'EGRESO', '#38bdf8', 'fa-plane'),
    ('Compras', 'Compras online', 'EGRESO', '#c084fc', 'fa-bag-shopping'),
    ('Educacion', 'Educación y cursos', 'EGRESO', '#facc15', 'fa-graduation-cap'),
    ('Otros', 'Otros Gastos', 'EGRESO', '#8b8b96', 'fa-ellipsis'),
    ('Suscripciones', 'Suscripciones', 'EGRESO', '#fb923c', 'fa-rotate'),
    ('Cuentas', 'Cuentas', 'EGRESO', '#e25c5c', 'fa-file-invoice'),
    ('Sueldo', 'Sueldo o salario', 'INGRESO', '#53d258', 'fa-money-check-dollar'),
    ('Freelance', 'Trabajo freelance', 'INGRESO', '#2fd8c8', 'fa-laptop-code'),
    ('Negocio', 'Negocio o emprendimiento', 'INGRESO', '#4b8cff', 'fa-store'),
    ('Venta', 'Venta de algo', 'INGRESO', '#a3e635', 'fa-tag'),
    ('Bono', 'Bono o aguinaldo', 'INGRESO', '#ffd54f', 'fa-gift'),
    ('Transferencia', 'Transferencia recibida', 'INGRESO', '#38bdf8', 'fa-right-left'),
    ('Otros_Ingresos', 'Otros ingresos', 'INGRESO', '#8b8b96', 'fa-ellipsis'),
)

MODELOS = ('Transaccion', 'TopeCategoria', 'GastoPendiente', 'Suscripcion', 'Deuda')


def crear_y_vincular(apps, schema_editor):
    Categoria = apps.get_model('finanzas', 'Categoria')
    for slug, nombre, tipo, color, icono in BASE:
        Categoria.objects.update_or_create(
            usuario=None, slug=slug,
            defaults={'nombre': nombre, 'tipo': tipo, 'color': color, 'icono': icono, 'activa': True})
    for nombre in MODELOS:
        modelo = apps.get_model('finanzas', nombre)
        for filtro in ({'usuario_id': OuterRef('usuario_id')}, {'usuario__isnull': True}):
            cat = Categoria.objects.filter(slug=OuterRef('categoria'), **filtro)
            (modelo.objects.filter(categoria_ref__isnull=True).filter(Exists(cat))
             .update(categoria_ref=Subquery(cat.values('id')[:1])))


def deshacer(apps, schema_editor):
    for nombre in MODELOS:
        apps.get_model('finanzas', nombre).objects.update(categoria_ref=None)
    apps.get_model('finanzas', 'Categoria').objects.filter(usuario__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0126_categoria_vinculo'),
    ]

    operations = [
        migrations.RunPython(crear_y_vincular, deshacer),
    ]
