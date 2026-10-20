from django.db.models import F, Q

from ..categorias_base import BASE
from ..models import Categoria, Deuda, GastoPendiente, Suscripcion, TopeCategoria, Transaccion

MODELOS = (Transaccion, TopeCategoria, GastoPendiente, Suscripcion, Deuda)


def filas_base():
    for slug, nombre, tipo, color, icono in BASE:
        yield {'slug': slug, 'nombre': nombre, 'tipo': tipo, 'color': color, 'icono': icono}


def asegurar_base():
    creadas = 0
    for fila in filas_base():
        slug = fila.pop('slug')
        _, nueva = Categoria.objects.get_or_create(usuario=None, slug=slug, defaults=fila)
        creadas += nueva
    return creadas


def desalineados(modelo):
    return modelo.objects.filter(
        Q(categoria_ref__usuario__isnull=False) & ~Q(categoria_ref__usuario=F('usuario')))


def revisar():
    return [{'tabla': modelo.__name__, 'total': modelo.objects.count(),
             'desalineados': desalineados(modelo).count()} for modelo in MODELOS]


def arreglar():
    asegurar_base()
    arregladas = 0
    for modelo in MODELOS:
        for fila in desalineados(modelo).select_related('categoria_ref'):
            fila.categoria = fila.categoria_ref.slug
            fila.save(update_fields=['categoria'])
            arregladas += 1
    return arregladas
