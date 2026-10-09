import hashlib
import json
import logging
import os

from django.core.cache import cache

log = logging.getLogger('finanzas')

DIAS_EN_CACHE = 30
POR_LLAMADA = 30


def _clave(a, b):
    crudo = json.dumps([[str(x[k]) for k in ('fecha', 'monto', 'tipo', 'categoria', 'descripcion')]
                        for x in sorted((a, b), key=lambda x: (str(x['fecha']), x['descripcion']))])
    return 'rep-ia:' + hashlib.sha256(crudo.encode()).hexdigest()


def _linea(x):
    tipo = 'ingreso' if x['tipo'] == 'INGRESO' else 'gasto'
    monto = f"{int(x['monto']):,}".replace(',', '.')
    desc = (x['descripcion'] or 'sin descripción')[:80]
    return f"{x['fecha']:%d/%m/%Y} · {tipo} · ${monto} · {x['categoria']} · «{desc}»"


def _prompt(lote):
    filas = '\n'.join(f'P{n}: A) {_linea(a)} | B) {_linea(b)}' for n, (_c, a, b) in enumerate(lote, 1))
    return f"""Revisas movimientos de una app de finanzas personales en Chile. En cada par, A y B son de la misma persona, tienen el mismo monto y fechas cercanas. Uno puede venir de la cartola del banco y el otro estar anotado a mano con otra descripción, o la misma cartola pudo importarse dos veces.

Decide en qué pares A y B son el mismo movimiento anotado dos veces. Dos compras distintas por el mismo monto, por ejemplo dos cafés o dos pasajes, no son el mismo si nada indica que se repitió. Si no estás seguro, no lo incluyas.

{filas}

Responde ÚNICAMENTE con JSON válido, sin markdown:
{{"iguales": ["P1"]}}"""


def _preguntar(cliente, lote):
    mensaje = cliente.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=400,
        messages=[{'role': 'user', 'content': _prompt(lote)}],
    )
    texto = ''.join(b.text for b in mensaje.content if b.type == 'text').strip()
    if texto.startswith('```'):
        texto = texto.split('```')[1]
        if texto.startswith('json'):
            texto = texto[4:]
    datos = json.loads(texto.strip())
    iguales = datos.get('iguales') if isinstance(datos, dict) else None
    if not isinstance(iguales, list):
        raise ValueError('respuesta sin la lista de iguales')
    return {str(x) for x in iguales}


def revisar_pares(pares):
    resultado, pendientes = {}, []
    for clave, a, b in pares:
        guardado = cache.get(_clave(a, b))
        if guardado is None:
            pendientes.append((clave, a, b))
        else:
            resultado[clave] = guardado
    if not pendientes:
        return resultado

    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        log.info('Revision de repetidos con IA no disponible: falta ANTHROPIC_API_KEY.')
        return resultado
    try:
        import anthropic
    except ImportError:
        log.warning('Revision de repetidos con IA no disponible: falta el paquete anthropic.')
        return resultado

    cliente = anthropic.Anthropic(api_key=api_key, timeout=20)
    for inicio in range(0, len(pendientes), POR_LLAMADA):
        lote = pendientes[inicio:inicio + POR_LLAMADA]
        try:
            iguales = _preguntar(cliente, lote)
        except json.JSONDecodeError:
            log.warning('La IA respondio algo que no es JSON valido al revisar repetidos.')
            continue
        except Exception:
            log.exception('Fallo la revision de repetidos con IA.')
            continue
        for n, (clave, a, b) in enumerate(lote, 1):
            veredicto = f'P{n}' in iguales
            resultado[clave] = veredicto
            cache.set(_clave(a, b), veredicto, DIAS_EN_CACHE * 24 * 3600)
    return resultado
