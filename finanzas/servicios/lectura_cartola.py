import logging
import secrets
import threading
from io import BytesIO

from django.core import signing
from django.core.cache import cache
from django.db import connections

from .. import cola

log = logging.getLogger('finanzas')

SAL = 'finanzas.cartola'
SEGUNDOS = 600
MAX_A_LA_VEZ = 2
_cupos = threading.BoundedSemaphore(MAX_A_LA_VEZ)


def a_dict(cartola):
    return {
        'banco': cartola.banco,
        'periodo': cartola.periodo,
        'cuenta': cartola.cuenta,
        'cuadra': cartola.cuadra,
        'descuadre': str(cartola.descuadre),
        'nota_cuadre': cartola.nota_cuadre,
        'saldo_inicial': str(cartola.saldo_inicial or ''),
        'saldo_final': str(cartola.saldo_final or ''),
        'movimientos': [{
            'fecha': m.fecha.isoformat(),
            'descripcion': m.descripcion,
            'monto': str(m.monto),
            'tipo': m.tipo,
            'categoria': m.categoria,
            'cuota_actual': m.cuota_actual,
            'cuota_total': m.cuota_total,
            'es_suscripcion': m.es_suscripcion,
            'ya_existe': m.ya_existe,
            'aviso': m.aviso,
            'fecha_compra': m.fecha_compra.isoformat() if m.fecha_compra else '',
            'mover_id': m.mover_id,
            'reemplaza_id': m.reemplaza_id,
            'reemplaza_seguro': m.reemplaza_seguro,
            'reemplaza_desc': m.reemplaza_desc,
            'reemplaza_fecha': m.reemplaza_fecha,
            'deuda_id': m.deuda_id,
            'deuda_periodo': m.deuda_periodo,
            'deuda_texto': m.deuda_texto,
            'prestamo_id': m.prestamo_id,
            'prestamo_texto': m.prestamo_texto,
            'vinculo_seguro': m.vinculo_seguro,
        } for m in cartola.movimientos],
    }


def leer_ahora(usuario, contenido, banco, nombre):
    from ..cartolas import enriquecer, leer_cartola
    from ..cartolas.base import ErrorCartola
    from ..cartolas.ciclo import reubicar_anteriores
    from ..cartolas.cuotas_conocidas import reconocer_cuotas
    from .repetidos import marcar_repetidas

    archivo = (nombre or '')[:80]
    try:
        cartola = leer_cartola(BytesIO(contenido), banco, nombre, usuario)
        enriquecer(cartola, usuario)
        reubicar_anteriores(cartola, usuario)
        reconocer_cuotas(cartola, usuario)
        marcar_repetidas(cartola, usuario)
    except ErrorCartola as e:
        return {'listo': True, 'ok': False, 'msg': str(e), 'muestra': getattr(e, 'muestra', ''),
                'archivo': archivo}
    except Exception:
        log.exception('Cartola ilegible')
        return {'listo': True, 'ok': False, 'msg': 'No se pudo leer la cartola.', 'archivo': archivo}
    return {'listo': True, 'ok': True, 'cartola': a_dict(cartola)}


def _clave(usuario_id, numero):
    return f'cartola:{usuario_id}:{numero}'


def _trabajar(usuario_id, contenido, banco, nombre, clave):
    from django.contrib.auth.models import User

    try:
        usuario = User.objects.get(pk=usuario_id)
        cache.set(clave, leer_ahora(usuario, contenido, banco, nombre), SEGUNDOS)
    except Exception:
        log.exception('La lectura de la cartola se cortó')
        cache.set(clave, {'listo': True, 'ok': False, 'msg': 'No se pudo leer la cartola.'}, SEGUNDOS)
    finally:
        _cupos.release()


def _en_hilo(*argumentos):
    try:
        _trabajar(*argumentos)
    finally:
        connections.close_all()


def lanzar(usuario, contenido, banco, nombre):
    if not _cupos.acquire(blocking=False):
        return None
    numero = secrets.token_urlsafe(12)
    clave = _clave(usuario.pk, numero)
    cache.set(clave, {'listo': False}, SEGUNDOS)
    argumentos = (usuario.pk, contenido, banco, nombre, clave)
    if cola.sincronica():
        _trabajar(*argumentos)
    else:
        try:
            threading.Thread(target=_en_hilo, args=argumentos, name='cartola', daemon=True).start()
        except RuntimeError:
            _cupos.release()
            cache.delete(clave)
            raise
    return signing.dumps({'u': usuario.pk, 'n': numero}, salt=SAL)


def estado(usuario, firmado):
    try:
        datos = signing.loads(firmado or '', salt=SAL, max_age=SEGUNDOS)
    except signing.BadSignature:
        return None
    if not isinstance(datos, dict) or datos.get('u') != usuario.pk:
        return None
    clave = _clave(usuario.pk, datos.get('n', ''))
    hecho = cache.get(clave)
    if hecho is None:
        return {'listo': True, 'ok': False, 'msg': 'Se perdió la lectura de la cartola. Súbela otra vez.'}
    if hecho.get('listo'):
        cache.delete(clave)
    return hecho
