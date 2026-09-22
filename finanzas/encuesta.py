from datetime import timedelta

from django.utils import timezone

SECCIONES = ['Inicio', 'Compras en cuotas', 'Me deben', 'Suscripciones', 'Estadísticas',
             'Análisis IA', 'Metas', 'Categorías', 'Importar cartola']
ANTIGUEDADES = ['Menos de 1 mes', '1 a 3 meses', '3 a 6 meses', 'Más de 6 meses']
FRECUENCIAS = ['Todos los días', 'Varias veces por semana', 'Una vez por semana', 'Menos seguido']
ANTIGUOS = ['3 a 6 meses', 'Más de 6 meses']

ABIERTAS = [
    ('gusta', 'Le gusta', '¿Qué es lo que más te gusta de la app?'),
    ('molesta', 'No le acomoda', '¿Qué no te acomoda o te ha costado?'),
    ('agregar', 'Agregaría', '¿Qué le agregarías?'),
    ('sacar', 'Sacaría', '¿Qué le sacarías o simplificarías?'),
    ('razon', 'Razón de la nota', '¿Qué te faltó para darnos un 10? / ¿Qué es lo que más valoras?'),
]

COOKIE_POSPUESTA = 'encuesta_pospuesta'
DIAS_POSPUESTA = 30
DIAS_MINIMOS_DE_USO = 14
DIAS_ENTRE_RESPUESTAS = 180

COLOR_NOTA = ['#e25c5c', '#ef8a5c', '#ffaa2c', '#a8d85a', '#53d258']
ETIQUETAS_FACILIDAD = ['1 · Muy difícil', '2', '3', '4', '5 · Muy fácil']


def antiguedad_de(usuario):
    dias = (timezone.now() - usuario.date_joined).days
    if dias < 30:
        return ANTIGUEDADES[0]
    if dias < 90:
        return ANTIGUEDADES[1]
    if dias < 180:
        return ANTIGUEDADES[2]
    return ANTIGUEDADES[3]


def debe_mostrar(request):
    from .models import RespuestaEncuesta
    usuario = request.user
    if not usuario.is_authenticated or request.COOKIES.get(COOKIE_POSPUESTA):
        return False
    ahora = timezone.now()
    if ahora - usuario.date_joined < timedelta(days=DIAS_MINIMOS_DE_USO):
        return False
    return not RespuestaEncuesta.objects.filter(
        usuario=usuario, creada__gte=ahora - timedelta(days=DIAS_ENTRE_RESPUESTAS)).exists()


def _coma(valor):
    return f'{valor:.1f}'.replace('.', ',')


def _ancho(parte, total):
    return f'{(parte / total * 100) if total else 0:.1f}%'


def _color_promedio(valor):
    if valor >= 4:
        return '#53d258'
    if valor >= 3:
        return '#ffaa2c'
    return '#e25c5c'


def colores_recomienda(valor):
    if valor <= 6:
        return 'rgba(226,92,92,.14)', '#e25c5c'
    if valor <= 8:
        return 'var(--surface-2)', 'var(--text-secondary)'
    return 'rgba(83,210,88,.14)', '#53d258'


def resumen(respuestas):
    total = len(respuestas)
    base = total or 1

    cuenta = [0] * 11
    for r in respuestas:
        cuenta[r.recomienda] += 1
    criticos, neutros, promotores = sum(cuenta[:7]), cuenta[7] + cuenta[8], cuenta[9] + cuenta[10]
    nps = round((promotores - criticos) / base * 100)
    tope = max(cuenta) or 1
    barras = [{
        'valor': v, 'n': c, 'alto': f'{c / tope * 82:.1f}%',
        'color': '#e25c5c' if v <= 6 else '#6a6a6a' if v <= 8 else '#53d258',
    } for v, c in enumerate(cuenta)]

    facil = [0] * 5
    for r in respuestas:
        facil[r.facilidad - 1] += 1
    facil_prom = sum(r.facilidad for r in respuestas) / base
    tope_f = max(facil) or 1
    filas_facilidad = [{
        'etiqueta': ETIQUETAS_FACILIDAD[i], 'n': c, 'pct': f'{round(c / base * 100)}%',
        'ancho': _ancho(c, tope_f), 'color': COLOR_NOTA[i],
    } for i, c in enumerate(facil)][::-1]

    secciones = []
    for s in SECCIONES:
        vals = [r.notas.get(s) for r in respuestas if isinstance(r.notas, dict) and r.notas.get(s)]
        dist = [0] * 5
        for v in vals:
            if 1 <= v <= 5:
                dist[v - 1] += 1
        prom = sum(vals) / len(vals) if vals else 0
        secciones.append({
            'nombre': s, 'n': len(vals), 'orden': prom,
            'prom': _coma(prom) if vals else '–',
            'color': _color_promedio(prom) if vals else 'var(--text-muted)',
            'partes': [{'color': COLOR_NOTA[i], 'ancho': _ancho(c, len(vals)), 'titulo': f'Nota {i + 1}: {c}'}
                       for i, c in enumerate(dist)],
        })
    secciones.sort(key=lambda x: (x['n'] > 0, x['orden']), reverse=True)
    evaluadas = [s for s in secciones if s['n']]
    peor = evaluadas[-1] if evaluadas else None

    return {
        'total': total,
        'nps': {
            'valor': f'+{nps}' if nps > 0 else str(nps),
            'color': '#53d258' if nps >= 30 else '#ffaa2c' if nps >= 0 else '#e25c5c',
            'criticos': f'{round(criticos / base * 100)}%', 'neutros': f'{round(neutros / base * 100)}%',
            'promotores': f'{round(promotores / base * 100)}%',
            'ancho_criticos': _ancho(criticos, base), 'ancho_neutros': _ancho(neutros, base),
            'ancho_promotores': _ancho(promotores, base),
            'barras': barras,
        },
        'facilidad': {
            'prom': _coma(facil_prom), 'color': _color_promedio(facil_prom),
            'faciles': f'{round((facil[3] + facil[4]) / base * 100)}%',
            'filas': filas_facilidad,
        },
        'secciones': secciones,
        'peor': peor,
        'leyenda_notas': [{'color': c, 'texto': str(i + 1)} for i, c in enumerate(COLOR_NOTA)],
    }
