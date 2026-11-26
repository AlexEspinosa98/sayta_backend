"""
Composición honesta de frases.

Cuando una frase no está completa en el glosario, se arma con las piezas que SÍ están, en el orden
del texto original, y lo que falta queda marcado entre corchetes: «Natue [come] arepa».
No se inventa ninguna palabra en la lengua; los huecos son exactamente las palabras que la
comunidad tendría que aportar. Cada hueco se registra como término faltante (ver
views_aprendizaje.registrar_faltantes) para que aparezca en la cola de validación.
"""
import re
from typing import Dict, List

from . import lexico

# Palabras funcionales del español que muchas veces no tienen equivalente léxico en ikʉn/kogui
# (artículos, preposiciones, conjunciones). Se marcan como hueco en la frase, pero NO se registran
# como término faltante: no son vocabulario que la comunidad deba "aportar".
_FUNCIONALES_ES = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'lo', 'al', 'del',
    'de', 'a', 'en', 'con', 'sin', 'por', 'para', 'sobre', 'entre', 'hacia', 'desde', 'hasta',
    'y', 'e', 'o', 'u', 'ni', 'que', 'se', 'le', 'les', 'me', 'te', 'nos',
    'es', 'esta', 'estan', 'son', 'hay', 'esta', 'este', 'esto', 'esa', 'ese', 'eso',
}
_PUNT = re.compile(r'^[\s,;:.!?¡¿"“”«»()\-]+$')


def componer(texto: str, direccion: str, piezas: List[Dict]) -> Dict:
    """
    Arma la frase a partir de las piezas (salida de lexico.piezas_en_texto) y marca los huecos.

    Devuelve:
      frase        «Natue [come] arepa»
      segmentos    [{'texto': 'Natue', 'tipo': 'pieza', 'origen': 'mi hermano', 'termino_lengua': 'Natue'},
                    {'texto': 'come',  'tipo': 'hueco', 'funcional': False}, ...]
      huecos       ['come', 'arepa']           palabras sin equivalente (sin las funcionales)
      cobertura    0.0–1.0                     fracción de palabras cubiertas por piezas
      completa     True si no quedó ningún hueco (ni funcional)
      piezas_audio ['Natue', ...]              términos en lengua, en orden, para la voz por piezas
    """
    toks = [t for t in re.split(r'\s+', texto.strip()) if t]
    n = len(toks)
    por_inicio: Dict[int, Dict] = {}
    for p in piezas:
        if p.get('inicio') is None or p.get('fin') is None:
            continue
        por_inicio[int(p['inicio'])] = p
    segmentos: List[Dict] = []
    huecos: List[str] = []
    cubiertos = 0
    i = 0
    while i < n:
        p = por_inicio.get(i)
        if p is not None and int(p['fin']) > i:
            equivalente = p['termino_lengua'] if direccion == 'es_a_lengua' else p['termino_es']
            segmentos.append({'texto': equivalente, 'tipo': 'pieza', 'origen': p['fragmento'],
                              'termino_lengua': p['termino_lengua'], 'termino_es': p['termino_es']})
            cubiertos += int(p['fin']) - i
            i = int(p['fin'])
            continue
        tok = toks[i]
        limpio = tok.strip(',;:.!?¡¿"“”«»()')
        if not limpio or _PUNT.match(tok):
            i += 1
            continue
        norm = lexico.normalizar(limpio)
        funcional = direccion == 'es_a_lengua' and norm in _FUNCIONALES_ES
        segmentos.append({'texto': limpio, 'tipo': 'hueco', 'funcional': funcional})
        if not funcional and norm and norm not in [lexico.normalizar(h) for h in huecos]:
            huecos.append(limpio)
        i += 1
    frase = ' '.join(s['texto'] if s['tipo'] == 'pieza' else f'[{s["texto"]}]' for s in segmentos)
    palabras = sum(1 for t in toks if not _PUNT.match(t))
    return {
        'frase': frase,
        'segmentos': segmentos,
        'huecos': huecos,
        'cobertura': round(cubiertos / palabras, 3) if palabras else 0.0,
        'completa': all(s['tipo'] == 'pieza' for s in segmentos) and bool(segmentos),
        'piezas_audio': [s['termino_lengua'] for s in segmentos if s['tipo'] == 'pieza'],
    }
