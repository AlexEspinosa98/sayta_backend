import json
import mimetypes
import os
import re
import unicodedata
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.http import FileResponse, JsonResponse, HttpRequest, HttpResponse
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

def _build_grabaciones_path() -> Path:
    base = Path(settings.BASE_DIR)
    for _ in range(4):
        base = base.parent
    return base / "mnt" / "sayta_data" / "data" / "Grabaciones"

GRABACIONES_BASE_PATH = _build_grabaciones_path()

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

AUDIO_EXTENSIONS = {".wav", ".mp3", ".mp4", ".m4a", ".ogg", ".flac"}


def _format_duration(total_seconds: float) -> str:
    total = int(total_seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}h {m:02d}m {s:02d}s"


def _audio_duration_seconds(path: Path) -> Optional[float]:
    try:
        if path.suffix.lower() == ".wav":
            import wave as _wave
            with _wave.open(str(path), "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        from mutagen import File as _MFile  # type: ignore
        af = _MFile(str(path))
        if af and af.info:
            return float(af.info.length)
    except Exception:
        pass
    return None


def _scan_audios_sin_procesar(session_dir: Path) -> Dict:
    folder = session_dir / "audios_sin_procesar"
    if not folder.exists() or not folder.is_dir():
        return {
            "total_audios": 0,
            "duracion_segundos": 0.0,
            "duracion_formateada": "0h 00m 00s",
            "sin_metadata": 0,
        }
    total = 0
    seconds = 0.0
    sin_meta = 0
    for f in sorted(folder.iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            total += 1
            d = _audio_duration_seconds(f)
            if d is not None:
                seconds += d
            else:
                sin_meta += 1
    return {
        "total_audios": total,
        "duracion_segundos": round(seconds, 2),
        "duracion_formateada": _format_duration(seconds),
        "sin_metadata": sin_meta,
    }


def _parse_session_name(name: str) -> Dict:
    # Formato esperado: grabacion_DD_MM_AA_tematica
    parts = name.split("_")
    result: Dict = {"fecha_texto": None, "fecha_iso": None, "tematica": None}
    if len(parts) >= 4 and parts[0].lower() == "grabacion":
        try:
            day, month, yy = int(parts[1]), int(parts[2]), int(parts[3])
            year = 2000 + yy if yy < 100 else yy
            result["fecha_iso"] = date(year, month, day).isoformat()
            result["fecha_texto"] = f"{day:02d}/{month:02d}/{year}"
            if len(parts) > 4:
                result["tematica"] = " ".join(parts[4:])
        except (ValueError, IndexError):
            pass
    return result


def _count_items_in_dir(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for _ in path.iterdir())


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


def _resolve_session_directory(community_dir: Path, session: str) -> Optional[Path]:
    session_dir = community_dir / session
    return session_dir if session_dir.exists() and session_dir.is_dir() else None


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


def recordings_debug_path_view(request: HttpRequest):
    pwd = Path(os.getcwd())

    pasos = []
    base = pwd
    for i in range(5):
        base = base.parent
        try:
            contenido = sorted(os.listdir(base))
        except PermissionError:
            contenido = ["(sin permiso)"]
        pasos.append({"nivel": i + 1, "path": str(base), "contenido": contenido})

    try:
        contenido_mnt = sorted(os.listdir("/mnt"))
    except Exception as e:
        contenido_mnt = [str(e)]

    return JsonResponse({
        "pwd": str(pwd),
        "grabaciones_base_path": str(GRABACIONES_BASE_PATH),
        "existe": GRABACIONES_BASE_PATH.exists(),
        "contenido_mnt": contenido_mnt,
        "pasos_cd_arriba": pasos,
    })


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
        sessions = _list_directories(community_dir)
        total_audios = 0
        total_seconds = 0.0
        sin_meta = 0
        for s in sessions:
            stats = _scan_audios_sin_procesar(s)
            total_audios += stats["total_audios"]
            total_seconds += stats["duracion_segundos"]
            sin_meta += stats["sin_metadata"]
        communities_summary.append(
            {
                "comunidad": community_dir.name,
                "total_jornadas": len(sessions),
                "total_archivos": _count_files_recursive(community_dir),
                "audios_sin_procesar": {
                    "total_audios": total_audios,
                    "duracion_segundos": round(total_seconds, 2),
                    "duracion_formateada": _format_duration(total_seconds),
                    "sin_metadata": sin_meta,
                },
            }
        )

    return JsonResponse(
        {
            "base_path": str(GRABACIONES_BASE_PATH),
            "total_comunidades": len(directories),
            "comunidades": communities_summary,
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
        audio_stats = _scan_audios_sin_procesar(rec)
        payload.append(
            {
                "nombre": rec.name,
                **_parse_session_name(rec.name),
                "total_items": _count_items_in_dir(rec),
                "audios_sin_procesar": audio_stats,
            }
        )

    total_audios = sum(j["audios_sin_procesar"]["total_audios"] for j in payload)
    total_seconds = sum(j["audios_sin_procesar"]["duracion_segundos"] for j in payload)

    return JsonResponse(
        {
            "comunidad": community_dir.name,
            "total_jornadas": len(payload),
            "resumen_audio": {
                "total_audios": total_audios,
                "duracion_formateada": _format_duration(total_seconds),
                "duracion_segundos": round(total_seconds, 2),
            },
            "jornadas": payload,
        }
    )


def _get_session_or_404(community: str, session: str):
    community_dir = _resolve_community_directory(GRABACIONES_BASE_PATH, community)
    if not community_dir:
        return None, None, JsonResponse(
            {"error": f"Comunidad '{community}' no encontrada."},
            status=404,
        )
    session_dir = _resolve_session_directory(community_dir, session)
    if not session_dir:
        return None, None, JsonResponse(
            {"error": f"Jornada '{session}' no encontrada en '{community_dir.name}'."},
            status=404,
        )
    return community_dir, session_dir, None


def session_audios_view(request: HttpRequest, community: str, session: str):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    _, session_dir, err = _get_session_or_404(community, session)
    if err:
        return err

    audios_folder = session_dir / "audios_sin_procesar"
    procesados_folder = session_dir / "audios_procesados"

    audios = []
    for f in sorted(audios_folder.iterdir()) if audios_folder.exists() else []:
        if not f.is_file() or f.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        d = _audio_duration_seconds(f)
        txt_path = procesados_folder / f"{f.stem}.txt"
        audios.append({
            "nombre": f.name,
            "extension": f.suffix.lower(),
            "tamaño_bytes": f.stat().st_size,
            "duracion_segundos": round(d, 2) if d is not None else None,
            "duracion_formateada": _format_duration(d) if d is not None else None,
            "etiquetado": txt_path.exists(),
        })

    return JsonResponse({
        "comunidad": community,
        "jornada": session,
        "total_audios": len(audios),
        "audios": audios,
    })


def session_audio_file_view(request: HttpRequest, community: str, session: str, filename: str):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    _, session_dir, err = _get_session_or_404(community, session)
    if err:
        return err

    audio_path = session_dir / "audios_sin_procesar" / filename
    if not audio_path.exists() or not audio_path.is_file():
        return JsonResponse({"error": f"Archivo '{filename}' no encontrado."}, status=404)

    content_type, _ = mimetypes.guess_type(str(audio_path))
    return FileResponse(
        open(audio_path, "rb"),
        content_type=content_type or "application/octet-stream",
        as_attachment=False,
    )


def session_glosario_view(request: HttpRequest, community: str, session: str):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    _, session_dir, err = _get_session_or_404(community, session)
    if err:
        return err

    glosario_path = session_dir / "glosario.json"
    if not glosario_path.exists():
        return JsonResponse({"error": "glosario.json no encontrado en esta jornada."}, status=404)

    with open(glosario_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JsonResponse(data, safe=False)


@csrf_exempt
def session_etiquetar_view(request: HttpRequest, community: str, session: str):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    _, session_dir, err = _get_session_or_404(community, session)
    if err:
        return err

    try:
        body = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    nombre_audio = body.get("nombre_audio", "").strip()
    etiqueta = body.get("etiqueta", "").strip()

    if not nombre_audio or not etiqueta:
        return JsonResponse({"error": "Faltan campos 'nombre_audio' y/o 'etiqueta'."}, status=400)

    audio_path = session_dir / "audios_sin_procesar" / nombre_audio
    if not audio_path.exists() or not audio_path.is_file():
        return JsonResponse({"error": f"Audio '{nombre_audio}' no encontrado."}, status=404)

    procesados_dir = session_dir / "audios_procesados"
    procesados_dir.mkdir(exist_ok=True)

    txt_path = procesados_dir / f"{Path(nombre_audio).stem}.txt"
    if txt_path.exists():
        return JsonResponse(
            {"error": f"Ya existe etiqueta para '{nombre_audio}'. Usa PUT para actualizar."},
            status=409,
        )

    txt_path.write_text(etiqueta, encoding="utf-8")
    return JsonResponse({
        "mensaje": "Etiqueta creada.",
        "audio": nombre_audio,
        "etiqueta": etiqueta,
        "archivo_txt": txt_path.name,
    }, status=201)


@csrf_exempt
def session_etiqueta_view(request: HttpRequest, community: str, session: str, filename: str):
    _, session_dir, err = _get_session_or_404(community, session)
    if err:
        return err

    stem = Path(filename).stem
    txt_path = session_dir / "audios_procesados" / f"{stem}.txt"

    if request.method == "GET":
        if not txt_path.exists():
            return JsonResponse({"error": "Etiqueta no encontrada."}, status=404)
        return JsonResponse({
            "audio": filename,
            "etiqueta": txt_path.read_text(encoding="utf-8").strip(),
            "archivo_txt": txt_path.name,
        })

    if request.method == "PUT":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido"}, status=400)
        etiqueta = body.get("etiqueta", "").strip()
        if not etiqueta:
            return JsonResponse({"error": "Falta el campo 'etiqueta'."}, status=400)
        (session_dir / "audios_procesados").mkdir(exist_ok=True)
        txt_path.write_text(etiqueta, encoding="utf-8")
        return JsonResponse({"mensaje": "Etiqueta actualizada.", "audio": filename, "etiqueta": etiqueta})

    if request.method == "DELETE":
        if not txt_path.exists():
            return JsonResponse({"error": "Etiqueta no encontrada."}, status=404)
        txt_path.unlink()
        return JsonResponse({"mensaje": "Etiqueta eliminada.", "audio": filename})

    return JsonResponse({"error": "Método no permitido"}, status=405)


def session_estado_view(request: HttpRequest, community: str, session: str):
    if request.method != "GET":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    _, session_dir, err = _get_session_or_404(community, session)
    if err:
        return err

    audios_folder = session_dir / "audios_sin_procesar"
    procesados_folder = session_dir / "audios_procesados"

    etiquetados = []
    sin_etiquetar = []

    for f in sorted(audios_folder.iterdir()) if audios_folder.exists() else []:
        if not f.is_file() or f.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        txt_path = procesados_folder / f"{f.stem}.txt"
        if txt_path.exists():
            etiquetados.append({
                "audio": f.name,
                "etiqueta": txt_path.read_text(encoding="utf-8").strip(),
                "archivo_txt": txt_path.name,
            })
        else:
            sin_etiquetar.append(f.name)

    return JsonResponse({
        "comunidad": community,
        "jornada": session,
        "total_audios": len(etiquetados) + len(sin_etiquetar),
        "total_etiquetados": len(etiquetados),
        "total_sin_etiquetar": len(sin_etiquetar),
        "porcentaje_completado": round(
            len(etiquetados) / (len(etiquetados) + len(sin_etiquetar)) * 100, 1
        ) if (etiquetados or sin_etiquetar) else 0,
        "etiquetados": etiquetados,
        "sin_etiquetar": sin_etiquetar,
    })
