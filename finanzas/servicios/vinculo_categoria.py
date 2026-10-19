from django.db.models import Exists, F, OuterRef, Q, Subquery

from ..models import Categoria, Deuda, GastoPendiente, Suscripcion, TopeCategoria, Transaccion

MODELOS = (Transaccion, TopeCategoria, GastoPendiente, Suscripcion, Deuda)

EXTRA_BASE = (
    ('Suscripciones', 'Suscripciones', 'EGRESO'),
    ('Cuentas', 'Cuentas', 'EGRESO'),
)


def filas_base():
    ingreso = {s for s, _ in Transaccion.CATEGORIAS_INGRESO}
    filas = [(s, n, 'INGRESO' if s in ingreso else 'EGRESO') for s, n in Transaccion.CATEGORIAS]
    for slug, nombre, tipo in filas + list(EXTRA_BASE):
        yield {
            'slug': slug, 'nombre': nombre, 'tipo': tipo,
            'color': Transaccion.COLORES_CATEGORIA.get(slug, Transaccion.COLORES_CATEGORIA['Otros']),
            'icono': Transaccion.ICONOS_CATEGORIA.get(slug, 'fa-tag'),
        }


def asegurar_base():
    creadas = 0
    for fila in filas_base():
        slug = fila.pop('slug')
        _, nueva = Categoria.objects.get_or_create(usuario=None, slug=slug, defaults=fila)
        creadas += nueva
    return creadas


def vincular(modelo):
    n = 0
    for filtro in ({'usuario_id': OuterRef('usuario_id')}, {'usuario__isnull': True}):
        cat = Categoria.objects.filter(slug=OuterRef('categoria'), **filtro)
        n += (modelo.objects.filter(categoria_ref__isnull=True).filter(Exists(cat))
              .update(categoria_ref=Subquery(cat.values('id')[:1])))
    return n


def sin_vinculo(modelo):
    return modelo.objects.filter(categoria_ref__isnull=True).exclude(categoria='')


def desalineados(modelo):
    return modelo.objects.filter(categoria_ref__isnull=False).filter(
        ~Q(categoria_ref__slug=F('categoria'))
        | (Q(categoria_ref__usuario__isnull=False) & ~Q(categoria_ref__usuario=F('usuario'))))


def revisar():
    salida = []
    for modelo in MODELOS:
        sueltos = sin_vinculo(modelo)
        salida.append({
            'tabla': modelo.__name__,
            'total': modelo.objects.count(),
            'sin_vinculo': sueltos.count(),
            'textos_sueltos': sorted(set(sueltos.values_list('categoria', flat=True))),
            'desalineados': desalineados(modelo).count(),
        })
    return salida


def arreglar():
    asegurar_base()
    vinculados = 0
    for modelo in MODELOS:
        desalineados(modelo).update(categoria_ref=None)
        vinculados += vincular(modelo)
    return vinculados
