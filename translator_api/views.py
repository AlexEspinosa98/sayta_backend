import json
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from .search_engine import load_metadata as se_load_metadata, semantic_search


# =============================
# Carga perezosa de recursos
# =============================

_metadata_cache: Optional[List[Dict]] = None
_lemma_index: Optional[Dict[str, Dict]] = None


def _load_metadata() -> Tuple[List[Dict], Dict[str, Dict]]:
    """Carga metadata.json (lemas y definiciones)."""
    global _metadata_cache, _lemma_index

    if _metadata_cache is not None:
        return _metadata_cache, _lemma_index

    _metadata_cache = se_load_metadata()

    _lemma_index = {entry.get("lemma", "").lower(): entry for entry in _metadata_cache}
    return _metadata_cache, _lemma_index


# =============================
# Utilidades de procesamiento
# =============================

SPANISH_PROFANITIES = {
    "puta", "puto", "mierda", "joder", "coño", "pendejo",
    "cabron", "cabrona", "carajo", "gonorrea", "estupido", "estúpido",
}

# Lista corta en Ette (placeholder). Si necesitas una lista real, amplíala aquí.
ETTE_PROFANITIES = {
    "aaǥa",  # ejemplo ilustrativo
}


def tokenize(text: str) -> List[str]:
    # Usa \w para capturar letras/números; la versión anterior buscaba un literal "\w"
    return re.findall("[\\w'áéíóúñü]+", text.lower())


def guardrail_node(tokens: List[str]) -> Dict:
    """Nodo 1: filtra groserías en español o Ette."""
    flagged = [t for t in tokens if t in SPANISH_PROFANITIES or t in ETTE_PROFANITIES]
    return {
        "allowed": len(flagged) == 0,
        "flagged_tokens": flagged,
        "message": "OK" if not flagged else "Mensaje bloqueado por lenguaje inapropiado",
    }


def render_sense(text: str, tokens: List[str], sense: Optional[Dict]) -> str:
    """Construye una frase legible escogiendo el mejor match por cada token."""
    if not sense or not sense.get("matches"):
        return f"No se encontraron coincidencias para '{text}'."

    matches = sense.get("matches", [])
    # Índice por token -> mejor match (mayor score; si no hay score toma el primero)
    best_by_token: Dict[str, Dict] = {}
    for m in matches:
        tok = m.get("token")
        if not tok:
            continue
        current = best_by_token.get(tok)
        # Decide si reemplazar
        if current is None:
            best_by_token[tok] = m
            continue
        cur_score = current.get("score")
        new_score = m.get("score")
        if cur_score is None and new_score is not None:
            best_by_token[tok] = m
        elif cur_score is not None and new_score is not None and new_score > cur_score:
            best_by_token[tok] = m

    rendered_parts = []
    for tok in tokens:
        m = best_by_token.get(tok)
        if not m:
            rendered_parts.append(tok)
            continue
        lemma = m.get("lemma") or tok
        definicion = m.get("definicion") or ""
        pos = m.get("pos")
        score = m.get("score")

        piece = f"{lemma}: {definicion}"
        if pos:
            piece += f" [{pos}]"
        if score is not None:
            piece += f" ({score:.2f})"
        rendered_parts.append(piece)

    return " | ".join(rendered_parts)


@lru_cache(maxsize=256)
def _semantic_search(token: str, top_k: int = 5) -> List[Dict]:
    """Consulta embeddings + FAISS y devuelve los mejores candidatos con score."""
    hits = semantic_search(token, top_k=top_k)
    for h in hits:
        h["token"] = token
    return hits


def sense_node(tokens: List[str]) -> Dict:
    """Nodo 2: recupera el significado usando embeddings + FAISS; cae a búsqueda léxica."""
    matches: List[Dict] = []
    errors: List[str] = []

    for t in tokens:
        try:
            hits = _semantic_search(t)
            if hits:
                matches.extend(hits)
                continue
        except Exception as exc:
            errors.append(str(exc))

        # Fallback si embeddings fallan
        _, lemma_index = _load_metadata()
        entry = lemma_index.get(t)
        if entry:
            matches.append({
                "token": t,
                "lemma": entry.get("lemma"),
                "definicion": entry.get("definicion"),
                "pos": entry.get("pos"),
                "sinonimos": entry.get("sinonimos", []),
                "score": None,
                "fallback": True,
            })

    return {
        "matches": matches,
        "errors": errors,
        "message": "Significados recuperados" if matches else "No se encontraron coincidencias",
    }


def run_langgraph_pipeline(text: str) -> Dict:
    tokens = tokenize(text)

    guard = guardrail_node(tokens)
    if not guard["allowed"]:
        return {
            "allowed": False,
            "guardrail": guard,
            "sense": None,
            "rendered_phrase": "Mensaje bloqueado por lenguaje inapropiado",
        }

    sense = sense_node(tokens)
    return {
        "allowed": True,
        "guardrail": guard,
        "sense": sense,
        "rendered_phrase": render_sense(text, tokens, sense),
    }


@csrf_exempt
def translate_view(request: HttpRequest):
    """Endpoint principal.

    - GET: devuelve ayuda rápida.
    - POST: recibe JSON {"frase": "..."} y ejecuta el pipeline.
    """
    if request.method == "GET":
        return JsonResponse({
            "message": "Envía la frase vía POST en el campo 'frase'",
            "example": {"frase": "hola mundo"},
        })

    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    debug_mode = False
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
        debug_mode = str(body.get("debug", "")).lower() in {"1", "true", "yes"}
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    if not debug_mode:
        debug_mode = str(request.GET.get("debug", "")).lower() in {"1", "true", "yes"}

    frase = body.get("frase") or body.get("sentence")
    if not frase:
        return JsonResponse({"error": "Falta el campo 'frase'"}, status=400)

    try:
        result = run_langgraph_pipeline(frase)
    except Exception as exc:  # captura errores de carga de metadata, etc.
        return JsonResponse({"error": str(exc)}, status=500)

    tokens = tokenize(frase)
    response = {
        "input": frase,
        "tokens": tokens,
        "result": result,
    }

    if debug_mode:
        response["debug"] = {
            "regex": "[\\w'áéíóúñü]+",
            "tokens": tokens,
            "matches": result.get("sense", {}).get("matches", []),
            "errors": result.get("sense", {}).get("errors", []),
        }

    return JsonResponse(response)
