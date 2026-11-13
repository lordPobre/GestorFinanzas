import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

from .. import fechas

FUENTE = 'https://mindicador.cl/api/{codigo}/{anio}'
CODIGOS = ('dolar', 'euro', 'uf', 'utm')
CLAVE = 'indicadores:hoy'
CLAVE_RESPALDO = 'indicadores:ultimo'
FRESCO = 60 * 60
SIN_RED = 5 * 60
GUARDADO = 14 * 24 * 60 * 60
ESPERA = 6
DIAS = 365


def _pedir(codigo, anio):
    pedido = urllib.request.Request(FUENTE.format(codigo=codigo, anio=anio),
                                    headers={'User-Agent': 'Fintora/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(pedido, timeout=ESPERA) as respuesta:
        datos = json.loads(respuesta.read().decode('utf-8'))
    salida = []
    for fila in datos.get('serie') or []:
        try:
            dia = datetime.fromisoformat(str(fila['fecha']).replace('Z', '+00:00')).date()
            salida.append((dia, float(fila['valor'])))
        except (KeyError, TypeError, ValueError):
            continue
    return salida


def _seguro(par):
    try:
        return _pedir(*par)
    except (OSError, ValueError):
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


def datos():
    listo = cache.get(CLAVE)
    if listo is not None:
        return listo
    hoy = fechas.hoy()
    pares = [(codigo, anio) for codigo in CODIGOS for anio in (hoy.year - 1, hoy.year)]
    with ThreadPoolExecutor(max_workers=len(pares)) as hilos:
        respuestas = dict(zip(pares, hilos.map(_seguro, pares), strict=True))
    viejo = (cache.get(CLAVE_RESPALDO) or {}).get('series') or {}
    series = {}
    for codigo in CODIGOS:
        partes = [respuestas[(codigo, anio)] for anio in (hoy.year - 1, hoy.year)]
        serie = _diaria([p for parte in partes if parte for p in parte], hoy) if partes[1] else []
        series[codigo] = serie or viejo.get(codigo) or []
    hay = any(series.values())
    nuevo = {'series': series, 'hay': hay, 'hora': timezone.localtime().strftime('%H:%M') if hay else ''}
    if hay:
        cache.set(CLAVE, nuevo, FRESCO)
        cache.set(CLAVE_RESPALDO, nuevo, GUARDADO)
    else:
        cache.set(CLAVE, nuevo, SIN_RED)
    return nuevo
