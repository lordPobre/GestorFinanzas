import json
import logging
import os
import re

log = logging.getLogger('finanzas')

LARGO_MAX = 700
CLAVE = re.compile(r'\[(D\d{1,2})\]')


def _plata(moneda, n):
    signo = '-' if n < 0 else ''
    return f'{signo}{moneda}{abs(int(n)):,}'.replace(',', '.')


def _prompt(r, moneda):
    p = lambda n: _plata(moneda, n)
    if r['deudas']:
        orden = 'menor saldo primero' if r['estrategia'] == 'saldo' else 'mayor cuota primero'
        deudas = '\n'.join(
            f"- [{d['clave']}]: debe {p(d['saldo'])}, cuota {p(d['cuota'])}, termina en "
            f"{d['termina']}" + (f", {d['meses_antes']} meses antes que sin extra" if d['meses_antes'] > 0 else '')
            for d in r['deudas'])
        bloque_deudas = (f"Orden elegido: {orden}. El extra va a la primera de la lista y, cuando termina, "
                         f"su cuota pasa a la siguiente.\n{deudas}\n"
                         f"Con el extra termina todo en {r['termina_todo']}. Sin extra terminaría en "
                         f"{r['termina_sin_extra']}.")
    else:
        bloque_deudas = 'No tiene deudas en cuotas.'

    fondo = (f"Completa el fondo en {r['fondo_completo_en']}." if r['fondo_completo_en']
             else ('Ya completó el fondo.' if r['porcentaje_fondo'] >= 100 else 'No está apartando para el fondo.'))

    return f"""Explica en español de Chile, a una persona, el plan que ella misma armó en una app de finanzas personales.

PLAN (moneda {moneda}):
- Le sobra al mes, después de gastos y cuotas: {p(r['sobra'])}
- Aparta para imprevistos: {p(r['ahorro'])} al mes
- Pone extra a sus deudas: {p(r['extra'])} al mes
- Queda sin destino: {p(r['libre'])}

DEUDAS:
{bloque_deudas}

FONDO PARA IMPREVISTOS:
- Meta (3 meses de gastos y cuotas): {p(r['meta_fondo'])}
- Lleva {p(r['llevas_fondo'])}, un {r['porcentaje_fondo']}%
- {fondo}

REGLAS:
- Usa solo estos números. No calcules cifras nuevas ni inventes montos, fechas ni tasas.
- No recomiendes productos financieros, instrumentos, bancos ni instituciones. No opines sobre pedir, renegociar ni consolidar créditos.
- Para nombrar una deuda escribe su clave tal cual, con corchetes, por ejemplo [D1].
- Tutea. Tono cercano y directo, sin jerga, sin exclamaciones y sin promesas.

Responde ÚNICAMENTE con JSON válido, sin markdown:
{{"parrafos": ["cómo reparte lo que le sobra", "el orden de las deudas y cuándo termina", "el fondo para imprevistos"]}}
Cada párrafo, de 1 a 3 frases."""


def _nombrar(texto, nombres):
    return CLAVE.sub(lambda m: f'«{nombres[m.group(1)]}»' if m.group(1) in nombres
                     else 'una de tus deudas', texto)


def explicar_plan(resumen, nombres, moneda='$'):
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        log.info('Plan con IA no disponible: falta ANTHROPIC_API_KEY.')
        return None
    try:
        import anthropic
    except ImportError:
        log.warning('Plan con IA no disponible: el paquete anthropic no esta instalado.')
        return None

    try:
        cliente = anthropic.Anthropic(api_key=api_key)
        mensaje = cliente.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=700,
            messages=[{'role': 'user', 'content': _prompt(resumen, moneda)}],
        )
        texto = ''.join(b.text for b in mensaje.content if b.type == 'text').strip()
        if texto.startswith('```'):
            texto = texto.split('```')[1]
            if texto.startswith('json'):
                texto = texto[4:]
        datos = json.loads(texto.strip())
    except json.JSONDecodeError:
        log.warning('La IA respondio algo que no es JSON valido en el plan.')
        return None
    except Exception:
        log.exception('Fallo la llamada a la API de Anthropic en el plan.')
        return None

    parrafos = datos.get('parrafos') if isinstance(datos, dict) else None
    if not isinstance(parrafos, list):
        return None
    limpios = [_nombrar(p.strip()[:LARGO_MAX], nombres)
               for p in parrafos[:4] if isinstance(p, str) and p.strip()]
    return limpios or None
