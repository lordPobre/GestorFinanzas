import logging
import os
import time
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

log = logging.getLogger('finanzas')

MODELOS = {
    'analisis': ('IA_MODELO_ANALISIS', 'claude-sonnet-4-6'),
    'plan': ('IA_MODELO_PLAN', 'claude-sonnet-4-6'),
    'repetidos': ('IA_MODELO_REPETIDOS', 'claude-sonnet-4-6'),
    'ayuda': ('IA_MODELO_AYUDA', 'claude-haiku-4-5'),
}
PRECIOS = {
    'claude-sonnet-4-6': (3.0, 15.0),
    'claude-haiku-4-5': (1.0, 5.0),
}
CAMPOS = ('llamadas', 'fallos', 'invalidas', 'entrada', 'salida', 'ms')
DIAS_DE_USO = 400


def modelo(funcion):
    variable, defecto = MODELOS[funcion]
    return os.environ.get(variable, '').strip() or defecto


def cliente(que, **opciones):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        log.info('%s no disponible: falta ANTHROPIC_API_KEY.', que)
        return None
    try:
        import anthropic
    except ImportError:
        log.warning('%s no disponible: el paquete anthropic no está instalado.', que)
        return None
    try:
        return anthropic.Anthropic(api_key=api_key, **opciones)
    except Exception:
        log.exception('%s no disponible: no se pudo crear el cliente de Anthropic.', que)
        return None


def herramienta(nombre, descripcion, propiedades):
    return {
        'name': nombre,
        'description': descripcion,
        'input_schema': {
            'type': 'object',
            'properties': propiedades,
            'required': list(propiedades),
            'additionalProperties': False,
        },
    }


def con_herramienta(h):
    return {'tools': [h], 'tool_choice': {'type': 'tool', 'name': h['name']}}


def datos_de(respuesta, nombre):
    for bloque in getattr(respuesta, 'content', None) or []:
        if getattr(bloque, 'type', '') == 'tool_use' and getattr(bloque, 'name', '') == nombre:
            datos = getattr(bloque, 'input', None)
            return datos if isinstance(datos, dict) else None
    return None


def _mes(hoy=None):
    return (hoy or timezone.localdate()).strftime('%Y-%m')


def _clave(mes, funcion, nombre, campo):
    return f'ia-uso:{mes}:{funcion}:{nombre}:{campo}'


def _sumar(clave, n):
    from .models import Contador

    if not n:
        return
    if Contador.objects.filter(clave=clave).update(cuenta=F('cuenta') + n):
        return
    try:
        with transaction.atomic():
            Contador.objects.create(clave=clave, cuenta=n,
                                    vence=timezone.now() + timedelta(days=DIAS_DE_USO))
    except IntegrityError:
        Contador.objects.filter(clave=clave).update(cuenta=F('cuenta') + n)


def _anotar(funcion, nombre, **cuentas):
    mes = _mes()
    try:
        for campo, n in cuentas.items():
            _sumar(_clave(mes, funcion, nombre, campo), n)
    except Exception:
        log.exception('No se pudo anotar el uso de la IA.')


def _tokens(uso, campo):
    try:
        return max(int(getattr(uso, campo, 0) or 0), 0)
    except (TypeError, ValueError):
        return 0


def llamar(cliente_ia, funcion, **datos):
    nombre = modelo(funcion)
    inicio = time.monotonic()
    try:
        respuesta = cliente_ia.messages.create(model=nombre, **datos)
    except Exception:
        _anotar(funcion, nombre, llamadas=1, fallos=1, ms=int((time.monotonic() - inicio) * 1000))
        raise
    ms = int((time.monotonic() - inicio) * 1000)
    uso = getattr(respuesta, 'usage', None)
    entrada, salida = _tokens(uso, 'input_tokens'), _tokens(uso, 'output_tokens')
    log.info('IA %s: %s respondió en %d ms con %d tokens de entrada y %d de salida.',
             funcion, nombre, ms, entrada, salida)
    _anotar(funcion, nombre, llamadas=1, ms=ms, entrada=entrada, salida=salida)
    return respuesta


def invalida(funcion):
    nombre = modelo(funcion)
    log.warning('IA %s: %s respondió sin el formato pedido.', funcion, nombre)
    _anotar(funcion, nombre, invalidas=1)


def uso_del_mes(mes=None):
    from .models import Contador

    prefijo = f'ia-uso:{mes or _mes()}:'
    filas = {}
    for clave, cuenta in Contador.objects.filter(clave__startswith=prefijo).values_list('clave', 'cuenta'):
        funcion, resto = clave[len(prefijo):].split(':', 1)
        nombre, campo = resto.rsplit(':', 1)
        fila = filas.setdefault((funcion, nombre), {'funcion': funcion, 'modelo': nombre,
                                                    **{c: 0 for c in CAMPOS}})
        if campo in CAMPOS:
            fila[campo] = cuenta
    salida = []
    for fila in sorted(filas.values(), key=lambda f: (f['funcion'], f['modelo'])):
        precio = PRECIOS.get(fila['modelo'])
        fila['dolares'] = (round((fila['entrada'] * precio[0] + fila['salida'] * precio[1]) / 1_000_000, 4)
                           if precio else None)
        salida.append(fila)
    return salida
