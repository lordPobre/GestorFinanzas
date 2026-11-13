import json
import logging
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

from .. import fechas

registro = logging.getLogger(__name__)

RECIENTE = 'https://indicadores.cl/api/v1/{codigo}.json'
HISTORICO = 'https://indicadores.cl/api/v1/historico/{codigo}/{anio}.json'
CODIGOS = ('dolar', 'euro', 'uf', 'utm')
CON_HISTORICO = ('dolar', 'uf')
CLAVE = 'indicadores:hoy'
CLAVE_RESPALDO = 'indicadores:ultimo'
FRESCO = 60 * 60
SIN_RED = 60
GUARDADO = 14 * 24 * 60 * 60
ESPERA = 8
DIAS = 365
CABECERAS = {'User-Agent': 'Fintora/1.0 (+https://indicadores.cl/api/)', 'Accept': 'application/json'}


def _dia(fila):
    if fila.get('fecha'):
        return date.fromisoformat(str(fila['fecha'])[:10])
    anio, mes = str(fila['mes'])[:7].split('-')
    return date(int(anio), int(mes), 1)


def _pedir(url):
    pedido = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(pedido, timeout=ESPERA) as respuesta:
        datos = json.loads(respuesta.read().decode('utf-8'))
    salida = []
    for fila in datos.get('serie') or []:
        try:
            salida.append((_dia(fila), float(fila['valor'])))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return salida


def _seguro(url):
    try:
        return _pedir(url)
    except (OSError, ValueError) as error:
        registro.warning('Indicadores: %s no respondió: %r', url, error)
        return None


def _diaria(puntos, hoy):
    mapa = dict(puntos)
    dia = hoy - timedelta(days=DIAS - 1)
    previos = [d for d in mapa if d < dia]
    ultimo = mapa[max(previos)] if previos else None
    salida = []
    while dia <= hoy:
        ultimo = mapa.get(dia, ultimo)
        if ultimo is not None:
            salida.append([dia.isoformat(), ultimo])
        dia += timedelta(days=1)
    return salida


def _serie(codigo, hoy):
    actual = _seguro(RECIENTE.format(codigo=codigo))
    if not actual:
        return []
    anterior = []
    if codigo in CON_HISTORICO:
        anterior = _seguro(HISTORICO.format(codigo=codigo, anio=hoy.year - 1)) or []
    return _diaria(anterior + actual, hoy)


def datos():
    listo = cache.get(CLAVE)
    if listo is not None:
        return listo
    hoy = fechas.hoy()
    with ThreadPoolExecutor(max_workers=len(CODIGOS)) as hilos:
        nuevas = dict(zip(CODIGOS, hilos.map(lambda c: _serie(c, hoy), CODIGOS), strict=True))
    viejo = (cache.get(CLAVE_RESPALDO) or {}).get('series') or {}
    series = {c: nuevas[c] or viejo.get(c) or [] for c in CODIGOS}
    hay = any(series.values())
    nuevo = {'series': series, 'hay': hay, 'hora': timezone.localtime().strftime('%H:%M') if hay else ''}
    if hay:
        cache.set(CLAVE, nuevo, FRESCO)
        cache.set(CLAVE_RESPALDO, nuevo, GUARDADO)
    else:
        registro.error('Indicadores: ninguna serie llegó desde indicadores.cl')
        cache.set(CLAVE, nuevo, SIN_RED)
    return nuevo
