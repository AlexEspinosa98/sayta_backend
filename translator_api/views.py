import json
import os
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .schema import OPENAPI_SCHEMA
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

GRABACIONES_BASE_PATH = Path(
    os.getenv("GRABACIONES_BASE_PATH", "/mnt/sayta_data/data/Grabaciones")
).resolve()

MONTHS_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

COMMUNITY_ALIASES = {
    "arhueco": "arhuaco",
    "arhuaco": "arhuaco",
    "iku": "arhuaco",
    "kogui": "kogui",
    "cogui": "kogui",
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower().strip())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _list_directories(base_path: Path) -> List[Path]:
    if not base_path.exists() or not base_path.is_dir():
        return []
    return sorted((p for p in base_path.iterdir() if p.is_dir()), key=lambda p: p.name.lower())


def _count_files_recursive(base_path: Path) -> int:
    if not base_path.exists() or not base_path.is_dir():
        return 0

    total = 0
    for current_root, _, files in os.walk(base_path):
        if not Path(current_root).is_dir():
            continue
        total += len(files)
    return total


def _resolve_community_directory(base_path: Path, community: str) -> Optional[Path]:
    directories = _list_directories(base_path)
    if not directories:
        return None

    requested = _normalize_text(community)
    canonical_requested = COMMUNITY_ALIASES.get(requested, requested)

    for directory in directories:
        normalized_name = _normalize_text(directory.name)
        canonical_name = COMMUNITY_ALIASES.get(normalized_name, normalized_name)
        if normalized_name == requested or canonical_name == canonical_requested:
            return directory

    return None


def _extract_date_info(folder_name: str) -> Dict[str, Optional[str]]:
    match = re.search(r"\b(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚÑa-záéíóúñ]+)", folder_name, flags=re.IGNORECASE)
    if not match:
        return {
            "fecha_texto": None,
            "fecha_iso": None,
        }

    day_value = int(match.group(1))
    month_text = _normalize_text(match.group(2))
    month_number = MONTHS_ES.get(month_text)
    if not month_number:
        return {
            "fecha_texto": f"{day_value} de {match.group(2)}",
            "fecha_iso": None,
        }

    current_year = date.today().year
    try:
        date_iso = date(current_year, month_number, day_value).isoformat()
    except ValueError:
        date_iso = None

    return {
        "fecha_texto": f"{day_value} de {match.group(2).lower()}",
        "fecha_iso": date_iso,
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


def select_best_matches(tokens: List[str], sense: Optional[Dict]) -> List[Dict]:
    """Devuelve el mejor match (mayor score) por token preservando el orden."""
    if not sense or not sense.get("matches"):
        return []

    matches = sense.get("matches", [])
    best_by_token: Dict[str, Dict] = {}
    for m in matches:
        tok = m.get("token")
        if not tok:
            continue
        current = best_by_token.get(tok)
        if current is None:
            best_by_token[tok] = m
            continue
        cur_score = current.get("score")
        new_score = m.get("score")
        if cur_score is None and new_score is not None:
            best_by_token[tok] = m
        elif cur_score is not None and new_score is not None and new_score > cur_score:
            best_by_token[tok] = m

    ordered = []
    for tok in tokens:
        m = best_by_token.get(tok)
        if m:
            ordered.append(m)
    return ordered


def render_sense(text: str, tokens: List[str], best_matches: List[Dict]) -> str:
    """Construye una frase legible con los mejores matches de cada token."""
    if not best_matches:
        return f"No se encontraron coincidencias para '{text}'."

    rendered_parts = []
    for tok in tokens:
        m = next((bm for bm in best_matches if bm.get("token") == tok), None)
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


def recordings_root_view(request: HttpRequest):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    directories = _list_directories(GRABACIONES_BASE_PATH)
    if not directories:
        return JsonResponse(
            {
                "base_path": str(GRABACIONES_BASE_PATH),
                "carpetas": [],
                "message": "No se encontraron carpetas o la ruta no existe.",
            },
            status=404,
        )

    communities_summary = []
    for community_dir in directories:
        recordings_dirs = _list_directories(community_dir)
        communities_summary.append(
            {
                "comunidad": community_dir.name,
                "path": str(community_dir),
                "total_grabaciones": len(recordings_dirs),
                "total_archivos": _count_files_recursive(community_dir),
            }
        )

    return JsonResponse(
        {
            "base_path": str(GRABACIONES_BASE_PATH),
            "carpetas": [d.name for d in directories],
            "total": len(directories),
            "resumen_comunidades": communities_summary,
        }
    )


def openapi_schema_view(request: HttpRequest):
    return JsonResponse(OPENAPI_SCHEMA)


_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Sayta API — Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/api/schema/",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      deepLinking: true,
      tryItOutEnabled: true,
    });
  </script>
</body>
</html>"""


def swagger_ui_view(request: HttpRequest):
    return HttpResponse(_SWAGGER_HTML, content_type="text/html")


def recordings_by_community_view(request: HttpRequest, community: str):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    community_dir = _resolve_community_directory(GRABACIONES_BASE_PATH, community)
    if community_dir is None:
        available = [d.name for d in _list_directories(GRABACIONES_BASE_PATH)]
        return JsonResponse(
            {
                "error": f"No se encontró la comunidad '{community}'.",
                "comunidades_disponibles": available,
            },
            status=404,
        )

    recordings = _list_directories(community_dir)
    payload = []
    for rec in recordings:
        payload.append(
            {
                "nombre": rec.name,
                "path": str(rec),
                **_extract_date_info(rec.name),
            }
        )

    return JsonResponse(
        {
            "comunidad": community_dir.name,
            "path": str(community_dir),
            "grabaciones": payload,
            "total": len(payload),
        }
    )
