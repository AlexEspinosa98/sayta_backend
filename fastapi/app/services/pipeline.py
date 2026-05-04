from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from app.config import DEFAULT_TOP_K
from app.services.search_engine import load_metadata as se_load_metadata
from app.services.search_engine import semantic_search

SPANISH_PROFANITIES = {
    "puta",
    "puto",
    "mierda",
    "joder",
    "coño",
    "pendejo",
    "cabron",
    "cabrona",
    "carajo",
    "gonorrea",
    "estupido",
    "estúpido",
}

ETTE_PROFANITIES = {
    "aaǥa",
}

_metadata_cache: Optional[List[Dict]] = None
_lemma_index: Optional[Dict[str, Dict]] = None


def _load_metadata() -> Tuple[List[Dict], Dict[str, Dict]]:
    global _metadata_cache, _lemma_index

    if _metadata_cache is not None:
        return _metadata_cache, _lemma_index or {}

    _metadata_cache = se_load_metadata()
    _lemma_index = {entry.get("lemma", "").lower(): entry for entry in _metadata_cache}
    return _metadata_cache, _lemma_index


def tokenize(text: str) -> List[str]:
    return re.findall("[\\w'áéíóúñü]+", text.lower())


def guardrail_node(tokens: List[str]) -> Dict:
    flagged = [t for t in tokens if t in SPANISH_PROFANITIES or t in ETTE_PROFANITIES]
    return {
        "allowed": len(flagged) == 0,
        "flagged_tokens": flagged,
        "message": "OK" if not flagged else "Mensaje bloqueado por lenguaje inapropiado",
    }


def select_best_matches(tokens: List[str], sense: Optional[Dict]) -> List[Dict]:
    if not sense or not sense.get("matches"):
        return []

    matches = sense.get("matches", [])
    best_by_token: Dict[str, Dict] = {}

    for match in matches:
        token = match.get("token")
        if not token:
            continue

        current = best_by_token.get(token)
        if current is None:
            best_by_token[token] = match
            continue

        current_score = current.get("score")
        new_score = match.get("score")
        if current_score is None and new_score is not None:
            best_by_token[token] = match
        elif current_score is not None and new_score is not None and new_score > current_score:
            best_by_token[token] = match

    ordered: List[Dict] = []
    for token in tokens:
        best = best_by_token.get(token)
        if best:
            ordered.append(best)

    return ordered


def render_sense(text: str, tokens: List[str], best_matches: List[Dict]) -> str:
    if not best_matches:
        return f"No se encontraron coincidencias para '{text}'."

    rendered_parts: List[str] = []
    for token in tokens:
        match = next((item for item in best_matches if item.get("token") == token), None)
        if not match:
            rendered_parts.append(token)
            continue

        lemma = match.get("lemma") or token
        definicion = match.get("definicion") or ""
        pos = match.get("pos")
        score = match.get("score")

        piece = f"{lemma}: {definicion}"
        if pos:
            piece += f" [{pos}]"
        if score is not None:
            piece += f" ({score:.2f})"
        rendered_parts.append(piece)

    return " | ".join(rendered_parts)


@lru_cache(maxsize=256)
def _semantic_search(token: str, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
    hits = semantic_search(token, top_k=top_k)
    for hit in hits:
        hit["token"] = token
    return hits


def sense_node(tokens: List[str]) -> Dict:
    matches: List[Dict] = []
    errors: List[str] = []

    for token in tokens:
        try:
            hits = _semantic_search(token)
            if hits:
                matches.extend(hits)
                continue
        except Exception as exc:
            errors.append(str(exc))

        _, lemma_index = _load_metadata()
        entry = lemma_index.get(token)
        if entry:
            matches.append(
                {
                    "token": token,
                    "lemma": entry.get("lemma"),
                    "definicion": entry.get("definicion"),
                    "pos": entry.get("pos"),
                    "sinonimos": entry.get("sinonimos", []),
                    "score": None,
                    "fallback": True,
                }
            )

    return {
        "matches": matches,
        "errors": errors,
        "message": "Significados recuperados" if matches else "No se encontraron coincidencias",
    }


def run_pipeline(text: str) -> Dict:
    tokens = tokenize(text)
    guard = guardrail_node(tokens)
    if not guard["allowed"]:
        return {
            "allowed": False,
            "guardrail": guard,
            "sense": None,
            "best_matches": [],
            "rendered_phrase": "Mensaje bloqueado por lenguaje inapropiado",
        }

    sense = sense_node(tokens)
    best_matches = select_best_matches(tokens, sense)
    return {
        "allowed": True,
        "guardrail": guard,
        "sense": sense,
        "best_matches": best_matches,
        "rendered_phrase": render_sense(text, tokens, best_matches),
    }
