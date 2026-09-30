import json
import re
import unicodedata
from functools import lru_cache

from django.conf import settings

RUTA = settings.BASE_DIR / 'static' / 'data' / 'marcas.json'


def normalizar(texto):
    t = unicodedata.normalize('NFKD', (texto or '').lower())
    return ''.join(c for c in t if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _tabla():
    with open(RUTA, encoding='utf-8') as archivo:
        datos = json.load(archivo)
    glifos = datos['glifos']
    tabla = []
    for m in datos['marcas']:
        claves = '|'.join(re.escape(c) for c in m['claves'])
        patron = re.compile(r'(?<![a-z0-9])(?:' + claves + r')(?![a-z0-9])')
        tabla.append((patron, {
            'nombre': m['nombre'],
            'fondo': m['fondo'],
            'tinta': m['tinta'],
            'd': glifos.get(m.get('glifo', '')),
            'fa': m.get('fa'),
            'letra': m.get('letra') or m['nombre'][:1].upper(),
        }))
    return tabla


def buscar_marca(texto):
    t = normalizar(texto)
    if not t:
        return None
    for patron, marca in _tabla():
        if patron.search(t):
            return marca
    return None
