"""Motor de búsqueda semántica basado en embeddings de Ette.

Extraído de `search.py` y adaptado para uso dentro de la API.
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, List
import json

import numpy as np
from django.conf import settings

MODEL_NAME = "intfloat/multilingual-e5-base"

_faiss_index = None
_st_model = None
_metadata_cache: List[Dict] | None = None


def _embeddings_dir() -> Path:
    base_dir = getattr(settings, "ETTE_EMBEDDINGS_DIR", None)
    if not base_dir:
        raise RuntimeError("ETTE_EMBEDDINGS_DIR no está configurado en settings.py")
    return Path(base_dir)


@lru_cache(maxsize=1)
def load_metadata() -> List[Dict]:
    """Carga metadata.json desde el directorio configurado."""
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    metadata_path = _embeddings_dir() / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"No se encontró metadata.json en {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        _metadata_cache = json.load(f)
    return _metadata_cache


def _load_faiss_and_model():
    """Carga FAISS y el modelo de embeddings sólo una vez."""
    global _faiss_index, _st_model

    if _faiss_index is not None and _st_model is not None:
        return _faiss_index, _st_model

    try:
        import faiss  # type: ignore
    except Exception as exc:
        raise RuntimeError("Dependencia 'faiss' no instalada") from exc

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:
        raise RuntimeError("Dependencia 'sentence-transformers' no instalada") from exc

    index_path = _embeddings_dir() / "faiss_index.bin"
    if not index_path.exists():
        raise FileNotFoundError(f"No se encontró faiss_index.bin en {index_path}")

    _faiss_index = faiss.read_index(str(index_path))
    _st_model = SentenceTransformer(MODEL_NAME)
    return _faiss_index, _st_model


@lru_cache(maxsize=256)
def semantic_search(query_text: str, top_k: int = 5) -> List[Dict]:
    """Realiza la búsqueda semántica (misma lógica que `search.py`)."""
    metadata = load_metadata()
    index, model = _load_faiss_and_model()

    query = "query: " + query_text
    query_embedding = model.encode([query], normalize_embeddings=True)
    query_embedding = np.array(query_embedding).astype("float32")

    distances, idxs = index.search(query_embedding, top_k)

    results = []
    for rank, idx in enumerate(idxs[0]):
        if idx >= len(metadata):
            continue
        score = 1 - float(distances[0][rank]) if distances.size else None
        entry = metadata[idx]
        results.append({
            "lemma": entry.get("lemma"),
            "definicion": entry.get("definicion"),
            "pos": entry.get("pos"),
            "sinonimos": entry.get("sinonimos", []),
            "score": score,
        })
    return results
