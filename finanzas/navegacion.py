from django.urls import reverse


def _entrada(clave, etiqueta, icono, **extra):
    return {'clave': clave, 'etiqueta': etiqueta, 'icono': icono, **extra}


ENTRADAS = (
    _entrada('dashboard', 'Inicio', 'fa-house', grupo='Tu mes', barra=True),
    _entrada('por_pagar', 'Por pagar', 'fa-list-check', grupo='Tu mes', barra=True),
    _entrada('deudas', 'Cuotas', 'fa-credit-card', grupo='Tu mes', barra=True, contador='cuotas_activas'),
    _entrada('prestamos', 'Préstamos', 'fa-hand-holding-dollar', grupo='Tu mes',
             contador='prestamos_activos', hoja=1, tinta='green'),
    _entrada('suscripciones', 'Suscripciones', 'fa-rotate', grupo='Tu mes',
             contador='subs_pendientes', hoja=3, tinta='orange'),
    _entrada('metas', 'Metas', 'fa-bullseye', grupo='Planificar', hoja=2, tinta='orange'),
    _entrada('plan_plata', 'Plan para tu plata', 'fa-route', grupo='Planificar', hoja=5, tinta='orange'),
    _entrada('analisis_predictivo', 'Análisis IA', 'fa-brain', grupo='Planificar', hoja=6, tinta='orange'),
    _entrada('estadisticas', 'Estadísticas', 'fa-chart-pie', grupo='Planificar', hoja=4, tinta='blue'),
    _entrada('importar_cartola', 'Importar cartola', 'fa-file-import', grupo='Datos', hoja=8, tinta='green',
             tambien=('revisar_cartola',)),
    _entrada('categorias', 'Categorías', 'fa-tags', grupo='Datos', hoja=7, tinta='blue'),
    _entrada('perfil', 'Mi perfil', 'fa-user', hoja=9, tinta='tile-avatar', avatar=True, cuenta=True),
    _entrada('encuesta', 'Danos tu opinión', 'fa-comment-dots', hoja=10, tinta='orange', cuenta=True),
    _entrada('encuesta_resultados', 'Resultados encuesta', 'fa-square-poll-vertical', hoja=11, tinta='blue',
             cuenta=True, solo_personal=True),
)

EN_LA_BARRA = frozenset(e['clave'] for e in ENTRADAS if e.get('barra'))


def armar(actual, contadores, es_personal):
    items = []
    for e in ENTRADAS:
        if e.get('solo_personal') and not es_personal:
            continue
        items.append({
            **e,
            'url': reverse(e['clave']),
            'activa': actual == e['clave'] or actual in e.get('tambien', ()),
            'cuenta_items': contadores.get(e['contador']) if e.get('contador') else None,
        })
    return items


def lateral(items):
    grupos = []
    for i in items:
        if not i.get('grupo'):
            continue
        if not grupos or grupos[-1]['titulo'] != i['grupo']:
            grupos.append({'titulo': i['grupo'], 'items': []})
        grupos[-1]['items'].append(i)
    return grupos


def barra(items):
    return [i for i in items if i.get('barra')]


def hoja(items):
    return sorted((i for i in items if i.get('hoja')), key=lambda i: i['hoja'])


def menu_cuenta(items):
    return [i for i in items if i.get('cuenta')]


def mas_activo(actual):
    return actual not in EN_LA_BARRA
