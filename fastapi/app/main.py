from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from app.services.pipeline import run_pipeline, tokenize

app = FastAPI(
    title="Traductor Espanol -> Ette",
    version="1.0.0",
    description="API independiente para traduccion semantica usando embeddings + FAISS.",
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí"}


@app.get("/traducir")
async def translate_help() -> Dict[str, Any]:
    return {
        "message": "Envia la frase via POST en el campo 'frase'",
        "example": {"frase": "hola mundo"},
    }


@app.post("/traducir")
async def translate_view(
    request: Request,
    debug: str | None = Query(default=None),
) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    except Exception:
        body = {}

    if not isinstance(body, dict):
        return JSONResponse({"error": "JSON inválido"}, status_code=400)

    debug_mode = _as_bool(body.get("debug")) or _as_bool(debug)
    phrase = body.get("frase") or body.get("sentence")
    if not phrase:
        return JSONResponse({"error": "Falta el campo 'frase'"}, status_code=400)

    try:
        result = run_pipeline(str(phrase))
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    tokens = tokenize(str(phrase))
    response: Dict[str, Any] = {
        "input": str(phrase),
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

    return JSONResponse(response)
