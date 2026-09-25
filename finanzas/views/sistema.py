import logging

from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.cache import cache_control


logger = logging.getLogger('finanzas')


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    ruta = finders.find('js/sw.js')
    if not ruta:
        raise Http404('sw.js no encontrado')
    with open(ruta, 'rb') as f:
        contenido = f.read()
    return HttpResponse(contenido, content_type='application/javascript')

@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def salud(request):
    from django.db import connection

    partes = {}
    ok = True

    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        partes['base'] = 'ok'
    except Exception as e:
        partes['base'] = 'error'
        ok = False
        logger.error('Health check: la base no responde (%s)', type(e).__name__)

    try:
        from django.core.cache import cache
        cache.set('salud', '1', 10)
        partes['cache'] = 'ok' if cache.get('salud') == '1' else 'error'
        if partes['cache'] == 'error':
            ok = False
    except Exception as e:
        partes['cache'] = 'error'
        ok = False
        logger.error('Health check: la caché no responde (%s)', type(e).__name__)

    return JsonResponse({'estado': 'ok' if ok else 'degradado', 'partes': partes},
                        status=200 if ok else 503)
