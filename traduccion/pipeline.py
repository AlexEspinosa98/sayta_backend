"""
Pipeline de traducción multi-estrategia.

Para una entrada de texto busca en tres niveles:
  1. Frase completa — captura frases compuestas del glosario (ej. "Tiwi kunse'")
  2. N-gramas (bi y tri-gramas) — captura subcombinaciones de palabras
  3. Tokens individuales — captura cada palabra por separado

Los resultados de los tres niveles se fusionan por término (lemma),
se enriquecen con termino_es desde la BD (compatibilidad con embeddings
anteriores a la inclusión de ese campo en el metadata) y se devuelven
los top_k ordenados por score.

Uso:
    pipeline = TranslationPipeline(engine, language_code='iku')
    results = pipeline.translate('Du zari bunsi chano', top_k=3)
"""

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# Penalización de score por nivel de análisis.
# Frase completa tiene prioridad; tokens individuales tienen la menor.
_WEIGHT_FULL = 1.00
_WEIGHT_NGRAM = 0.92
_WEIGHT_TOKEN = 0.80

# Umbral mínimo de score para incluir un resultado
_MIN_SCORE = 0.30


def _tokenize(text: str) -> List[str]:
    """Divide el texto respetando caracteres especiales del ikʉn (apóstrofes, diacríticos)."""
    return [t for t in re.split(r'\s+', text.strip()) if t]


def _build_ngrams(tokens: List[str], max_n: int = 3) -> List[str]:
    """Genera todos los bi y tri-gramas posibles de la lista de tokens."""
    ngrams = []
    n = len(tokens)
    for size in range(2, min(n + 1, max_n + 1)):
        for i in range(n - size + 1):
            ngrams.append(' '.join(tokens[i:i + size]))
    return ngrams


def _calcular_probabilidades(results: List[Dict]) -> List[Dict]:
    """
    Convierte los scores coseno en probabilidades relativas (suman 100 %).
    Marca el primer resultado como mejor_coincidencia.
    """
    if not results:
        return results
    total = sum(r['score'] for r in results)
    for i, r in enumerate(results):
        r['probabilidad'] = round((r['score'] / total) * 100, 1) if total > 0 else 0.0
        r['mejor_coincidencia'] = (i == 0)
    return results


def _enrich_with_db(results: List[Dict], language_code: str) -> List[Dict]:
    """
    Rellena termino_es vacío consultando la BD por lemma.
    Un solo SELECT para todos los resultados sin termino_es.
    Compatible con embeddings generados antes de que se añadiera termino_es al metadata.
    """
    sin_es = [r for r in results if not r.get('termino_es')]
    if not sin_es:
        return results

    lemmas = [r['termino'] for r in sin_es]
    try:
        from terminos.models import TerminoLeng
        db_map = {
            t.termino: t.termino_es.termino
            for t in TerminoLeng.objects.filter(
                termino__in=lemmas,
                lengua__codigo=language_code,
                termino_es__isnull=False,
            ).select_related('termino_es')
        }
        for r in results:
            if not r.get('termino_es') and r['termino'] in db_map:
                r['termino_es'] = db_map[r['termino']]
    except Exception as exc:
        logger.warning('No se pudo enriquecer termino_es desde BD: %s', exc)

    return results


class TranslationPipeline:
    """
    Ejecuta la búsqueda semántica en tres niveles y fusiona los resultados.
    """

    def __init__(self, engine, language_code: str):
        self._engine = engine
        self._language_code = language_code

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def translate(self, texto: str, top_k: int = 3) -> List[Dict]:
        tokens = _tokenize(texto)
        candidates: Dict[str, Dict] = {}

        # Nivel 1 — frase completa
        self._search_and_merge(texto, candidates, weight=_WEIGHT_FULL)

        if len(tokens) > 1:
            # Nivel 2 — n-gramas
            for ngram in _build_ngrams(tokens):
                self._search_and_merge(ngram, candidates, weight=_WEIGHT_NGRAM)

            # Nivel 3 — tokens individuales (omitir tokens muy cortos)
            for token in tokens:
                if len(token) > 2:
                    self._search_and_merge(token, candidates, weight=_WEIGHT_TOKEN)

        # Filtrar por umbral mínimo y ordenar
        valid = [r for r in candidates.values() if r['score'] >= _MIN_SCORE]
        ranked = sorted(valid, key=lambda r: r['score'], reverse=True)[:top_k]

        # Enriquecer con termino_es desde BD si el metadata no lo tenía
        enriched = _enrich_with_db(ranked, self._language_code)

        # Calcular probabilidad relativa y marcar el mejor
        return _calcular_probabilidades(enriched)

    # ------------------------------------------------------------------
    # Privado
    # ------------------------------------------------------------------

    def _search_and_merge(self, query: str, candidates: Dict[str, Dict], weight: float) -> None:
        """
        Busca `query` en el índice FAISS y fusiona los hits en `candidates`.
        Para cada término guarda solo el hit con mayor score ajustado.
        """
        try:
            hits = self._engine.search(query, language_code=self._language_code, top_k=5)
        except Exception as exc:
            logger.debug('Búsqueda fallida para "%s": %s', query, exc)
            return

        for hit in hits:
            lemma = hit.get('lemma')
            if not lemma:
                continue
            raw_score = hit.get('score') or 0.0
            adjusted = round(raw_score * weight, 4)
            existing = candidates.get(lemma)
            if existing is None or adjusted > existing['score']:
                candidates[lemma] = {
                    'termino': lemma,
                    'termino_es': hit.get('termino_es') or '',
                    'definicion': hit.get('definicion') or '',
                    'pos': hit.get('pos') or '',
                    'score': adjusted,
                    'coincidencia': query,
                }
