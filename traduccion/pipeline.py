"""
Pipeline de traducción de SAYTA.

Orden de trabajo:
  1. Capa léxica (traduccion.lexico): coincidencia exacta / aproximada / parcial con el glosario,
     y patrones productivos de la lengua. Una coincidencia exacta siempre va primera (confianza 100).
  2. Búsqueda semántica (embeddings + FAISS) en tres niveles: frase completa, n-gramas y palabras.
     Su similitud coseno se convierte en una confianza ABSOLUTA (0–100), no relativa entre resultados.
  3. Fusión por término, orden por confianza y aviso cuando nada parece estar en el glosario.

Cada resultado trae:
  termino, termino_es, definicion, pos, score, confianza (0–100), nivel
  ('exacta' | 'aproximada' | 'parcial' | 'alta' | 'media' | 'baja'), fuente ('glosario' | 'patrón' | 'semántica'),
  coincidencia (sub-consulta que lo encontró), nota, hipotesis (True si la entrada aún no fue validada
  con hablantes), probabilidad (= confianza, por compatibilidad) y mejor_coincidencia.

Uso:
    pipeline = TranslationPipeline(engine, language_code='Kogui')
    r = pipeline.traducir('Jiba kalde malde', direccion='lengua_a_es', top_k=3)
    r['resultados'], r['en_glosario'], r['aviso']
"""
import logging
import re
from typing import Dict, List, Optional

from . import lexico

logger = logging.getLogger(__name__)

_WEIGHT_FULL = 1.00
_WEIGHT_NGRAM = 0.94
_WEIGHT_TOKEN = 0.86

# Similitud coseno (e5, consultas cortas) → confianza absoluta.
# Medido sobre el glosario: aciertos ≈ 0,65–0,80; texto fuera del glosario ≈ 0,55–0,71.
_COS_MIN, _COS_MAX = 0.55, 0.82
_UMBRAL_EN_GLOSARIO = 70     # confianza mínima para considerar que el texto sí está en el glosario


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r'\s+', text.strip()) if t]


def _build_ngrams(tokens: List[str], max_n: int = 3) -> List[str]:
    ngrams = []
    n = len(tokens)
    for size in range(2, min(n + 1, max_n + 1)):
        for i in range(n - size + 1):
            ngrams.append(' '.join(tokens[i:i + size]))
    return ngrams


def confianza_semantica(score: float) -> int:
    if score is None:
        return 0
    c = (score - _COS_MIN) / (_COS_MAX - _COS_MIN) * 100
    return int(round(max(0, min(100, c))))


def nivel_semantico(conf: int) -> str:
    return 'alta' if conf >= 70 else ('media' if conf >= 45 else 'baja')


def _enrich_with_db(results: List[Dict], language_code: str) -> List[Dict]:
    sin_es = [r for r in results if not r.get('termino_es')]
    if not sin_es:
        return results
    try:
        from terminos.models import TerminoLeng
        db_map = {
            t.termino: t.termino_es.termino
            for t in TerminoLeng.objects.filter(termino__in=[r['termino'] for r in sin_es], lengua__codigo=language_code, termino_es__isnull=False).select_related('termino_es')
        }
        for r in results:
            if not r.get('termino_es') and r['termino'] in db_map:
                r['termino_es'] = db_map[r['termino']]
    except Exception as exc:
        logger.warning('No se pudo enriquecer termino_es desde BD: %s', exc)
    return results


class TranslationPipeline:
    def __init__(self, engine, language_code: str):
        self._engine = engine
        self._language_code = language_code

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def traducir(self, texto: str, direccion: str = 'lengua_a_es', top_k: int = 3, solo_lexico: bool = False) -> Dict:
        """solo_lexico=True: respuesta rápida (glosario + patrones, sin embeddings ni verificador) para sugerencias mientras se escribe."""
        texto = (texto or '').strip()
        candidatos: Dict[str, Dict] = {}

        # 1) capa léxica y patrones
        lexicos = []
        try:
            lexicos = lexico.buscar_patrones(texto, self._language_code, direccion) + lexico.buscar_lexico(texto, self._language_code, direccion)
        except Exception as exc:
            logger.warning('Capa léxica falló (%s); se continúa con semántica', exc)
        for r in lexicos:
            prev = candidatos.get(r['termino'])
            if prev is None or r['confianza'] > prev['confianza']:
                candidatos[r['termino']] = r

        # 2) semántica (si hay motor para la lengua)
        errores_semantica: Optional[str] = None
        try:
            if not solo_lexico:
                self._semantica(texto, candidatos)
        except ValueError as exc:          # lengua sin embedding activo
            errores_semantica = str(exc)
            if not candidatos:
                raise
        except Exception as exc:
            errores_semantica = str(exc)
            logger.warning('Búsqueda semántica falló: %s', exc)

        ranked = sorted(candidatos.values(), key=lambda r: (-r['confianza'], r['fuente'] != 'glosario'))[:top_k]
        ranked = _enrich_with_db(ranked, self._language_code)
        for i, r in enumerate(ranked):
            r['probabilidad'] = float(r['confianza'])
            r['mejor_coincidencia'] = (i == 0)

        en_glosario = bool(ranked) and (ranked[0]['fuente'] in ('glosario', 'patrón') and ranked[0]['confianza'] >= 60 or ranked[0]['confianza'] >= _UMBRAL_EN_GLOSARIO)
        aviso = None
        if not ranked:
            aviso = 'No se encontró ninguna entrada parecida en el glosario.'
        elif not en_glosario:
            aviso = 'Este texto no parece estar en el glosario. Se muestran las entradas más parecidas, pero pueden no corresponder.'
        elif ranked[0].get('hipotesis'):
            aviso = 'La mejor coincidencia es una hipótesis derivada del análisis de frases, aún no validada con hablantes.'
        elif ranked[0]['fuente'] == 'patrón':
            aviso = ranked[0].get('nota') or None
        if errores_semantica and not ranked:
            aviso = errores_semantica

        return {'resultados': ranked, 'en_glosario': en_glosario, 'aviso': aviso}

    def translate(self, texto: str, top_k: int = 3, direccion: str = 'lengua_a_es') -> List[Dict]:
        """Compatibilidad con el código anterior: solo la lista de resultados."""
        return self.traducir(texto, direccion=direccion, top_k=top_k)['resultados']

    # ------------------------------------------------------------------
    # Privado
    # ------------------------------------------------------------------

    def _semantica(self, texto: str, candidatos: Dict[str, Dict]) -> None:
        tokens = _tokenize(texto)
        self._search_and_merge(texto, candidatos, weight=_WEIGHT_FULL)
        if len(tokens) > 1:
            for ngram in _build_ngrams(tokens):
                self._search_and_merge(ngram, candidatos, weight=_WEIGHT_NGRAM)
            for token in tokens:
                if len(token) > 2:
                    self._search_and_merge(token, candidatos, weight=_WEIGHT_TOKEN)

    def _search_and_merge(self, query: str, candidatos: Dict[str, Dict], weight: float) -> None:
        hits = self._engine.search(query, language_code=self._language_code, top_k=5)
        for hit in hits:
            lemma = hit.get('lemma')
            if not lemma:
                continue
            raw = hit.get('score') or 0.0
            conf = confianza_semantica(raw * weight)
            prev = candidatos.get(lemma)
            if prev is not None and prev['confianza'] >= conf:
                continue
            candidatos[lemma] = {
                'termino': lemma, 'termino_es': hit.get('termino_es') or '', 'definicion': hit.get('definicion') or '',
                'pos': hit.get('pos') or '', 'score': round(raw * weight, 4), 'confianza': conf, 'nivel': nivel_semantico(conf),
                'fuente': 'semántica', 'coincidencia': query, 'nota': '',
                'hipotesis': (hit.get('tipo_morfema') or '') == 'hipótesis',
            }
