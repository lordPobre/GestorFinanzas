import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import encuesta as enc
from .models import RespuestaEncuesta


def _entero(valor, minimo, maximo):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    return numero if minimo <= numero <= maximo else None


def _texto(post, campo):
    return (post.get(campo) or '').strip()[:2000]


@login_required(login_url='/login/')
def encuesta(request):
    error = False
    if request.method == 'POST':
        p = request.POST
        facilidad = _entero(p.get('facilidad'), 1, 5)
        recomienda = _entero(p.get('recomienda'), 0, 10)
        secciones = [s for s in p.getlist('secciones') if s in enc.SECCIONES]
        if facilidad is not None and recomienda is not None and secciones:
            notas = {}
            for i, s in enumerate(enc.SECCIONES):
                nota = _entero(p.get(f'nota_{i}'), 1, 5)
                if s in secciones and nota:
                    notas[s] = nota
            antiguedad = p.get('antiguedad')
            frecuencia = p.get('frecuencia')
            RespuestaEncuesta.objects.create(
                usuario=request.user,
                antiguedad=antiguedad if antiguedad in enc.ANTIGUEDADES else enc.antiguedad_de(request.user),
                frecuencia=frecuencia if frecuencia in enc.FRECUENCIAS else '',
                facilidad=facilidad,
                secciones=secciones,
                notas=notas,
                gusta=_texto(p, 'gusta'),
                molesta=_texto(p, 'molesta'),
                agregar=_texto(p, 'agregar'),
                sacar=_texto(p, 'sacar'),
                recomienda=recomienda,
                razon=_texto(p, 'razon'),
            )
            messages.success(request, 'Gracias por responder la encuesta.')
            return redirect('dashboard')
        error = True

    return render(request, 'finanzas/encuesta.html', {
        'error': error,
        'antiguedades': enc.ANTIGUEDADES,
        'frecuencias': enc.FRECUENCIAS,
        'secciones': list(enumerate(enc.SECCIONES)),
        'escala5': range(1, 6),
        'escala10': range(0, 11),
    })


@login_required(login_url='/login/')
@require_POST
def encuesta_posponer(request):
    respuesta = redirect('dashboard')
    respuesta.set_cookie(enc.COOKIE_POSPUESTA, '1', max_age=enc.DIAS_POSPUESTA * 86400,
                         httponly=True, samesite='Lax', secure=request.is_secure())
    return respuesta


def _csv(respuestas):
    salida = HttpResponse(content_type='text/csv; charset=utf-8')
    salida['Content-Disposition'] = f'attachment; filename="encuesta-{timezone.localdate():%Y-%m-%d}.csv"'
    salida.write('\ufeff')
    w = csv.writer(salida, delimiter=';')
    w.writerow(['Fecha', 'Usuario', 'Antigüedad', 'Frecuencia', 'Facilidad', 'Secciones']
               + [f'Nota {s}' for s in enc.SECCIONES]
               + ['Le gusta', 'No le acomoda', 'Agregaría', 'Sacaría', 'Recomienda', 'Razón'])
    for r in respuestas:
        notas = r.notas if isinstance(r.notas, dict) else {}
        w.writerow([timezone.localtime(r.creada).strftime('%Y-%m-%d %H:%M'), r.usuario.username,
                    r.antiguedad, r.frecuencia, r.facilidad, ', '.join(r.secciones or [])]
                   + [notas.get(s, '') for s in enc.SECCIONES]
                   + [r.gusta, r.molesta, r.agregar, r.sacar, r.recomienda, r.razon])
    return salida


@login_required(login_url='/login/')
def encuesta_resultados(request):
    if not request.user.is_staff:
        raise Http404

    grupo = request.GET.get('grupo', 'todos')
    qs = RespuestaEncuesta.objects.select_related('usuario').order_by('-creada')
    if grupo == 'nuevos':
        qs = qs.exclude(antiguedad__in=enc.ANTIGUOS)
    elif grupo == 'antiguos':
        qs = qs.filter(antiguedad__in=enc.ANTIGUOS)
    else:
        grupo = 'todos'

    if request.GET.get('formato') == 'csv':
        return _csv(qs)

    respuestas = list(qs)
    datos = enc.resumen(respuestas)

    ids = [a[0] for a in enc.ABIERTAS]
    pestana = request.GET.get('p') if request.GET.get('p') in ids else 'molesta'
    busqueda = (request.GET.get('q') or '').strip()
    limite = _entero(request.GET.get('n'), 1, 100000) or 20
    base_url = reverse('encuesta_resultados')

    def enlace(**cambios):
        params = {'grupo': grupo, 'p': pestana, 'q': busqueda}
        params.update(cambios)
        return base_url + '?' + urlencode({k: v for k, v in params.items() if v not in ('', None)})

    def con_texto(campo):
        return [r for r in respuestas
                if getattr(r, campo) and (not busqueda or busqueda.lower() in getattr(r, campo).lower())]

    pestanas = [{'id': i, 'texto': t, 'n': len(con_texto(i)), 'on': i == pestana, 'url': enlace(p=i)}
                for i, t, _ in enc.ABIERTAS]
    todos = con_texto(pestana)
    comentarios = []
    for r in todos[:limite]:
        fondo, color = enc.colores_recomienda(r.recomienda)
        comentarios.append({'texto': getattr(r, pestana), 'recomienda': r.recomienda, 'fondo': fondo,
                            'color': color, 'creada': r.creada, 'antiguedad': r.antiguedad.lower(),
                            'facilidad': r.facilidad})

    grupos = [{'texto': t, 'on': g == grupo, 'url': enlace(grupo=g)}
              for g, t in [('todos', 'Todos'), ('nuevos', 'Nuevos (< 3 meses)'), ('antiguos', 'Antiguos (3+ meses)')]]

    return render(request, 'finanzas/encuesta_resultados.html', {
        **datos,
        'grupos': grupos,
        'grupo': grupo,
        'pestanas': pestanas,
        'pestana': pestana,
        'pregunta_actual': next(a[2] for a in enc.ABIERTAS if a[0] == pestana),
        'busqueda': busqueda,
        'comentarios': comentarios,
        'restantes': max(0, len(todos) - limite),
        'url_mas': enlace(n=limite + 20),
        'url_csv': base_url + '?' + urlencode({'grupo': grupo, 'formato': 'csv'}),
    })
