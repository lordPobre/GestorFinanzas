import logging
import time
from contextvars import ContextVar

from django.conf import settings
from django.db import connection

logger = logging.getLogger('finanzas')

_memo = ContextVar('finanzas_memo', default=None)


def recordar(clave, calcular):
    memo = _memo.get()
    if memo is None:
        return calcular()
    if clave not in memo:
        memo[clave] = calcular()
    return memo[clave]


def limpiar():
    memo = _memo.get()
    if memo is not None:
        memo.clear()


class RendimientoMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        consultas = [0]

        def contar(ejecutar, sql, params, many, contexto):
            consultas[0] += 1
            return ejecutar(sql, params, many, contexto)

        token = _memo.set({})
        inicio = time.perf_counter()
        try:
            with connection.execute_wrapper(contar):
                respuesta = self.get_response(request)
        finally:
            _memo.reset(token)
        ms = round((time.perf_counter() - inicio) * 1000)

        usuario = getattr(request, 'user', None)
        if settings.DEBUG or getattr(usuario, 'is_staff', False):
            respuesta['Server-Timing'] = f'app;dur={ms}, db;desc="{consultas[0]} consultas"'
        if ms >= getattr(settings, 'RESPUESTA_LENTA_MS', 1500):
            coincidencia = getattr(request, 'resolver_match', None)
            ruta = coincidencia.route if coincidencia else request.path
            logger.warning('Respuesta lenta: %s %s, %s ms, %s consultas',
                           request.method, ruta, ms, consultas[0])
        return respuesta
