"""
Traducción con varios agentes:

  1. Proponente  — el pipeline (glosario + patrones + semántica) produce candidatos y las
                   «piezas» del glosario que aparecen dentro del texto.
  2. Verificador — un modelo de lenguaje local (Ollama, qwen2.5) revisa si la mejor opción tiene
                   sentido, puede elegir otra candidata o componer una traducción usando SOLO las
                   piezas del glosario cuando el texto es una frase que junta varias entradas.
  3. Guardián    — comprobación determinista de la salida del verificador: índice válido, nada
                   inventado fuera del glosario (hacia la lengua), confianza acotada. Si el modelo
                   no responde a tiempo, el resultado del proponente se entrega tal cual con
                   verificacion.estado = 'no_disponible'.

Configuración (settings o variables de entorno):
  OLLAMA_URL            http://cits-ollama:11434
  OLLAMA_MODELO         qwen2.5:7b
  TRADUCCION_VERIFICAR  1/0 (por defecto 1)
  TRADUCCION_VERIFICAR_TIMEOUT  segundos (por defecto 25)
"""
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from django.conf import settings

from . import lexico

logger = logging.getLogger(__name__)


def _cfg(nombre: str, defecto):
    return getattr(settings, nombre, os.environ.get(nombre, defecto))


def activo() -> bool:
    return str(_cfg('TRADUCCION_VERIFICAR', '1')).lower() in ('1', 'true', 'si', 'sí', 'yes')


def _llamar_llm(prompt: str, timeout: float) -> Dict:
    url = str(_cfg('OLLAMA_URL', 'http://cits-ollama:11434')).rstrip('/') + '/api/generate'
    modelo = str(_cfg('OLLAMA_MODELO', 'qwen2.5:7b'))
    cuerpo = json.dumps({'model': modelo, 'prompt': prompt, 'stream': False, 'format': 'json', 'keep_alive': '2h',
                         'options': {'temperature': 0.1, 'num_predict': 320}}).encode('utf-8')
    req = urllib.request.Request(url, data=cuerpo, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        datos = json.loads(resp.read().decode('utf-8'))
    texto = datos.get('response', '')
    m = re.search(r'\{.*\}', texto, re.S)
    salida = json.loads(m.group(0) if m else texto)
    salida['_modelo'] = modelo
    return salida


def _prompt(texto: str, direccion: str, lengua: str, candidatos: List[Dict], piezas: List[Dict]) -> str:
    origen, destino = ('español', lengua) if direccion == 'es_a_lengua' else (lengua, 'español')
    lineas = []
    for i, c in enumerate(candidatos, 1):
        lineas.append(f'{i}. "{c["termino"]}" = "{c["termino_es"]}" (confianza {c["confianza"]}, {c["nivel"]}, {c["fuente"]})'
                      + (f' — {c["definicion"][:160]}' if c.get('definicion') else ''))
    piezas_txt = '\n'.join(f'- "{p["fragmento"]}" = "{p["equivalente"]}"' for p in piezas) or '- (ninguna)'
    regla_destino = ('La traducción final debe estar en ' + destino + '. ' +
                     ('Cuando compongas en ' + lengua + ' usa ÚNICAMENTE palabras que aparezcan en los candidatos o en las piezas; está prohibido inventar palabras en ' + lengua + '.'
                      if direccion == 'es_a_lengua' else 'Escribe el español de forma natural y completa.'))
    return f"""Eres un verificador experto de traducciones entre español y la lengua {lengua} (Sierra Nevada de Santa Marta, Colombia), para un sistema de salud intercultural. No conoces {lengua} más allá del glosario que te doy: no inventes nada.

Texto de entrada ({origen}): "{texto}"
Dirección: {origen} → {destino}

Candidatos propuestos por el buscador (número, término en {lengua} = equivalente en español):
{chr(10).join(lineas) or '(ninguno)'}

Piezas del glosario encontradas DENTRO del texto (útiles si hay que componer):
{piezas_txt}

Tareas:
1. Decide si alguno de los candidatos traduce correctamente TODO el texto. Si es así, "eleccion" es su número y "compuesta" es false. Si un candidato solo cubre UNA PARTE del texto, no lo des por bueno: usa las piezas para componer (tarea 2) y anota lo que falte en "sin_traducir".
2. Si ningún candidato cubre todo el texto pero las piezas sí lo cubren en gran parte, compón la traducción a partir de las piezas ("compuesta": true, "eleccion": null) y di qué partes quedaron sin traducir.
3. Si nada corresponde, "coherente": false, "eleccion": null, "traduccion_final": "".
{regla_destino}
"explicacion": una o dos frases en español, claras para personal de salud, diciendo por qué.
"confianza": 0-100 según qué tan seguro estás de la traducción final.

Responde SOLO con JSON con exactamente estas claves:
{{"eleccion": <número o null>, "coherente": true|false, "compuesta": true|false, "traduccion_final": "<texto>", "sin_traducir": ["<fragmentos>"], "explicacion": "<texto>", "confianza": <0-100>}}"""


def _cobertura(texto: str, parte: str) -> float:
    """Fracción de las palabras del texto que están en `parte` (normalizadas)."""
    t = lexico.normalizar(texto).split()
    p = set(lexico.normalizar(parte).split())
    return (sum(1 for w in t if w in p) / len(t)) if t else 1.0


def _resto_sin_cubrir(texto: str, parte: str) -> str:
    p = set(lexico.normalizar(parte).split())
    return ' '.join(w for w in re.split(r'\s+', texto.strip()) if lexico.normalizar(w) and lexico.normalizar(w) not in p)


def _tokens_permitidos(texto: str, candidatos: List[Dict], piezas: List[Dict]) -> set:
    """
    Vocabulario con el que el verificador puede componer: las piezas halladas DENTRO del texto y
    las candidatas cuyo lado español realmente aparece en el texto. Una candidata que solo se parece
    semánticamente («buenas tardes» para «mi hermano come arepa») no puede colarse en la composición.
    """
    permitidos = set()
    t_norm = ' ' + lexico.normalizar(texto) + ' '
    for c in candidatos:
        es = lexico.normalizar(c.get('termino_es', ''))
        if es and (' ' + es + ' ') in t_norm:
            permitidos.update(lexico.normalizar(c['termino']).split())
    for p in piezas:
        permitidos.update(lexico.normalizar(p['termino_lengua']).split())
    return permitidos


def verificar(texto: str, direccion: str, lengua_codigo: str, lengua_nombre: str, resultados: List[Dict]) -> Dict:
    """
    Devuelve {'resultados': lista (posiblemente reordenada / con una entrada compuesta al inicio),
              'verificacion': {...}}.
    """
    inicio = time.time()
    piezas = []
    try:
        piezas = lexico.piezas_en_texto(texto, lengua_codigo, direccion)
    except Exception as exc:
        logger.warning('piezas_en_texto falló: %s', exc)

    # Composición honesta: la frase armada solo con piezas del glosario y los huecos marcados.
    # Se adjunta siempre que haya piezas; el front la muestra cuando ninguna candidata cubre todo.
    honesta = None
    if piezas:
        try:
            from . import composicion
            honesta = composicion.componer(texto, direccion, piezas)
        except Exception as exc:
            logger.warning('composicion.componer falló: %s', exc)

    base = {'estado': 'no_disponible', 'eleccion': None, 'traduccion_final': None, 'explicacion': '', 'confianza': None,
            'sin_traducir': [], 'modelo': None, 'ms': 0, 'piezas': piezas, 'compuesta_honesta': honesta}
    if not activo() or (not resultados and not piezas):
        base['estado'] = 'omitida' if not activo() else 'sin_coincidencia'
        base['ms'] = int((time.time() - inicio) * 1000)
        return {'resultados': resultados, 'verificacion': base}

    candidatos = resultados[:5]
    try:
        salida = _llamar_llm(_prompt(texto, direccion, lengua_nombre, candidatos, piezas), float(_cfg('TRADUCCION_VERIFICAR_TIMEOUT', 25)))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning('Verificador no disponible: %s', exc)
        base['explicacion'] = 'El verificador no respondió; se muestra el resultado del buscador sin verificar.'
        base['ms'] = int((time.time() - inicio) * 1000)
        return {'resultados': resultados, 'verificacion': base}

    # ── Guardián ──────────────────────────────────────────────────────────
    ver = dict(base)
    ver['modelo'] = salida.get('_modelo')
    ver['explicacion'] = str(salida.get('explicacion') or '').strip()[:400]
    ver['sin_traducir'] = [str(x)[:80] for x in (salida.get('sin_traducir') or []) if x][:6]
    try:
        conf_llm = int(max(0, min(100, float(salida.get('confianza') or 0))))
    except (TypeError, ValueError):
        conf_llm = 0
    coherente = bool(salida.get('coherente', True))
    eleccion = salida.get('eleccion')
    compuesta = bool(salida.get('compuesta')) and bool(str(salida.get('traduccion_final') or '').strip())
    final = str(salida.get('traduccion_final') or '').strip()

    nuevos = list(resultados)
    try:
        idx = int(eleccion) - 1 if eleccion is not None else None
    except (TypeError, ValueError):
        idx = None

    if idx is not None and 0 <= idx < len(candidatos) and not compuesta:
        elegido = nuevos[idx]
        # el verificador no puede subir una candidata floja a «segura» sin más
        tope = min(100, elegido['confianza'] + 25) if elegido['confianza'] < 60 else 100
        ver['confianza'] = min(conf_llm, tope)
        ver['eleccion'] = idx
        ver['traduccion_final'] = (elegido['termino'] if direccion == 'es_a_lengua' else elegido['termino_es']) if not final else final
        ver['estado'] = 'confirmada' if idx == 0 else 'ajustada'
        # cobertura: ¿la candidata abarca todo el texto o solo un trozo?
        lado = elegido['termino'] if direccion == 'lengua_a_es' else elegido['termino_es']
        cobertura = _cobertura(texto, lado)
        if cobertura < 0.7:
            ver['estado'] = 'parcial'
            ver['confianza'] = min(ver['confianza'] or 0, int(cobertura * 100) + 10)
            resto = _resto_sin_cubrir(texto, lado)
            if resto and resto not in ver['sin_traducir']:
                ver['sin_traducir'].append(resto)
            ver['explicacion'] = (ver['explicacion'] + ' ').strip() + ' [Guardián: la opción cubre solo una parte del texto.]'
        elegido = dict(elegido, verificado=True)
        nuevos = [elegido] + [r for i, r in enumerate(nuevos) if i != idx]
    elif compuesta:
        valida = True
        if direccion == 'es_a_lengua':
            permitidos = _tokens_permitidos(texto, candidatos, piezas)
            fuera = [t for t in lexico.normalizar(final).split() if t not in permitidos]
            if fuera:
                valida = False
                ver['explicacion'] = (ver['explicacion'] + ' ').strip() + f' [Rechazada por el guardián: usa palabras fuera del glosario: {", ".join(fuera[:5])}]'
        if valida and piezas:
            cobertura = sum(len(p['fragmento']) for p in piezas) / max(len(texto), 1)
            ver['confianza'] = min(conf_llm, int(40 + 50 * min(cobertura, 1)))
            ver['eleccion'] = None
            ver['traduccion_final'] = final
            ver['estado'] = 'compuesta'
            termino, es = (final, texto) if direccion == 'es_a_lengua' else (texto, final)
            compuesto = {'termino': termino, 'termino_es': es, 'pos': 'FRS',
                         'definicion': 'Traducción compuesta por el verificador a partir de piezas del glosario: ' + '; '.join(f'«{p["fragmento"]}» = {p["equivalente"]}' for p in piezas[:8]) + '. Conviene confirmarla con un hablante.',
                         'score': round(ver['confianza'] / 100, 4), 'confianza': ver['confianza'], 'nivel': 'compuesta', 'fuente': 'verificador',
                         'coincidencia': texto, 'nota': 'Compuesta a partir de piezas del glosario; verificar con hablante.', 'hipotesis': False, 'verificado': True}
            nuevos = [compuesto] + nuevos
        else:
            ver['estado'] = 'rechazada'
            ver['confianza'] = None
    elif not coherente:
        ver['estado'] = 'sin_coincidencia'
        ver['confianza'] = conf_llm
    else:
        ver['estado'] = 'no_concluyente'
        ver['confianza'] = None

    for i, r in enumerate(nuevos):
        r['mejor_coincidencia'] = (i == 0)
        r['probabilidad'] = float(r.get('confianza', 0))
    ver['ms'] = int((time.time() - inicio) * 1000)
    return {'resultados': nuevos, 'verificacion': ver}
