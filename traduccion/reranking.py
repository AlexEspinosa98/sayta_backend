"""
Reordenamiento de hipótesis del reconocedor de voz (ASR) con evidencia del glosario.

El ASR devuelve varias transcripciones candidatas (n-best). La primera es la más probable
acústicamente, pero en lenguas con poco entrenamiento suele confundir palabras parecidas.
Aquí cada candidata recibe una «evidencia léxica»: cuánto de ella coincide con entradas del
glosario (exactas o aproximadas) y qué fracción del texto queda cubierta por piezas conocidas.
Se elige la candidata con más evidencia; en empate se respeta el orden del ASR.
"""
from typing import Dict, List, Tuple

from . import lexico


def evidencia(texto: str, codigo: str) -> Dict:
    hits = lexico.buscar_lexico(texto, codigo, 'lengua_a_es', max_resultados=3)
    mejor = max((h['confianza'] for h in hits if h['nivel'] in ('exacta', 'aproximada')), default=0)
    parcial = max((h['confianza'] for h in hits if h['nivel'] == 'parcial'), default=0)
    piezas = lexico.piezas_en_texto(texto, codigo, 'lengua_a_es')
    toks = max(len(lexico.normalizar(texto).split()), 1)
    cubiertos = sum(p['fin'] - p['inicio'] for p in piezas)
    cobertura = min(cubiertos / toks, 1.0)
    puntaje = mejor + 0.4 * parcial + 25 * cobertura
    return {'texto': texto, 'puntaje': round(puntaje, 1), 'mejor_lexica': mejor, 'cobertura': round(cobertura, 2), 'piezas': len(piezas)}


def elegir_transcripcion(alternativas: List[str], codigo: str, margen: float = 8.0) -> Tuple[int, List[Dict]]:
    """
    Devuelve (índice elegido, detalle por alternativa). Solo se cambia la primera opción del ASR
    cuando otra la supera en evidencia por al menos `margen` puntos (evita cambios por ruido).
    """
    alts = [a for a in alternativas if a and a.strip()]
    if not alts:
        return 0, []
    detalle = [evidencia(a, codigo) for a in alts]
    mejor_i = 0
    for i, d in enumerate(detalle[1:], 1):
        if d['puntaje'] > detalle[mejor_i]['puntaje'] + (margen if mejor_i == 0 else 0):
            mejor_i = i
    for i, d in enumerate(detalle):
        d['elegida'] = (i == mejor_i)
        d['orden_asr'] = i
    return mejor_i, detalle
