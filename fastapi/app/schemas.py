from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class TranslateRequest(BaseModel):
    frase: str | None = None
    sentence: str | None = None
    debug: bool | str | int | None = None


class TranslateResponse(BaseModel):
    input: str
    tokens: List[str]
    result: Dict[str, Any]
    debug: Dict[str, Any] | None = None
