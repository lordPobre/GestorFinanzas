"""
Capa de IA: interpreta el análisis financiero (números) y genera
un diagnóstico en lenguaje natural con recomendaciones personalizadas.

Usa la API de Anthropic (Claude). Si no hay API key o falla,
la app sigue funcionando con solo los números del motor determinístico.
"""
import os
import json


def _construir_prompt(analisis, moneda='$'):
    factores_texto = "\n".join(
        f"- {f['factor']}: {f['detalle']}" for f in analisis['riesgo_factores']
    )

    return f"""Eres un asesor financiero experto y empático. Analiza la situación financiera de esta persona y da un diagnóstico claro y accionable EN ESPAÑOL.

DATOS FINANCIEROS (moneda: {moneda}):
- Ingreso mensual promedio: {moneda}{analisis['ingreso_mensual']:,}
- Gasto mensual promedio: {moneda}{analisis['gasto_mensual']:,}
- Cuota mensual de deudas: {moneda}{analisis['cuota_mensual_total']:,}
- Deuda total restante: {moneda}{analisis['deuda_total_restante']:,}
- Flujo libre mensual (lo que queda): {moneda}{analisis['flujo_libre']:,}
- Ratio deuda/ingreso (DTI): {analisis['dti']}%
- Meses restantes hasta saldar todo: {analisis['meses_restantes']}
- Cantidad de deudas activas: {analisis['cantidad_deudas']}
- Nivel de riesgo calculado: {analisis['riesgo_nivel']} (score {analisis['riesgo_score']}/100)
- Tendencia de la deuda: {analisis['tendencia']}

FACTORES DE RIESGO DETECTADOS:
{factores_texto}

Responde ÚNICAMENTE con un JSON válido (sin markdown, sin ```), con esta estructura exacta:
{{
  "diagnostico": "2-3 frases que resuman la situación de forma directa y humana",
  "recomendaciones": ["consejo accionable 1", "consejo accionable 2", "consejo accionable 3"],
  "proyeccion_texto": "1-2 frases sobre qué pasará si mantiene el ritmo actual",
  "mensaje_motivacional": "1 frase de aliento realista, sin falsas promesas"
}}

Sé concreto, usa los números reales, y evita jerga financiera complicada. Habla directo a la persona (tú/tu)."""


def interpretar_con_ia(analisis, moneda='$'):
    """
    Llama a la API de Anthropic para interpretar el análisis.
    Devuelve dict con el diagnóstico, o None si falla / no hay API key.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        return None

    if not analisis.get('tiene_datos'):
        return None

    try:
        import anthropic
    except ImportError:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _construir_prompt(analisis, moneda)

        mensaje = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        texto = ""
        for bloque in mensaje.content:
            if bloque.type == 'text':
                texto += bloque.text

        texto = texto.strip()
        if texto.startswith('```'):
            texto = texto.split('```')[1]
            if texto.startswith('json'):
                texto = texto[4:]
            texto = texto.strip()

        datos = json.loads(texto)

        if 'diagnostico' in datos and 'recomendaciones' in datos:
            return datos
        return None

    except Exception:
        return None
