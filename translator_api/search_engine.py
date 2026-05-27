"""
Motor de búsqueda semántica multi-lengua.

Mantiene compatibilidad con el motor original Ette (single-language) y agrega
soporte para múltiples lenguas indígenas cargadas dinámicamente desde la BD.

Clase principal: MultiLanguageSearchEngine (singleton)
Función legacy:  semantic_search(query, top_k)  → sigue funcionando igual
"""

import json
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Motor de una sola lengua
# ---------------------------------------------------------------------------


class SingleLanguageEngine:
    """
    Motor de búsqueda semántica para una lengua.
    Encapsula el modelo SentenceTransformer y el índice FAISS.
    """

    def __init__(self, faiss_path: str, metadata_path: str, model_name: str):
        self._faiss_path = faiss_path
        self._metadata_path = metadata_path
        self._model_name = model_name
        self._index = None
        self._model = None
        self._metadata: List[Dict] = []
        self._lock = threading.Lock()
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()

    def _load(self):
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("Dependencia 'faiss-cpu' no instalada") from exc

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Dependencia 'sentence-transformers' no instalada") from exc

        self._index = faiss.read_index(self._faiss_path)

        with open(self._metadata_path, 'r', encoding='utf-8') as f:
            self._metadata = json.load(f)

        self._model = SentenceTransformer(self._model_name)
        self._loaded = True
        logger.info('Motor cargado: model=%s faiss=%s', self._model_name, self._faiss_path)

    def search(self, query_text: str, top_k: int = 5) -> List[Dict]:
        self._ensure_loaded()

        query = 'query: ' + query_text
        query_emb = self._model.encode([query], normalize_embeddings=True)
        query_emb = np.array(query_emb).astype('float32')

        distances, idxs = self._index.search(query_emb, top_k)

        results = []
        for rank, idx in enumerate(idxs[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            score = float(1 - distances[0][rank]) if distances.size else None
            entry = self._metadata[idx]
            results.append({
                'lemma': entry.get('lemma'),
                'termino_es': entry.get('termino_es', ''),
                'definicion': entry.get('definicion'),
                'pos': entry.get('pos'),
                'sinonimos': entry.get('sinonimos', []),
                'score': score,
            })
        return results


# ---------------------------------------------------------------------------
# Motor multi-lengua (singleton)
# ---------------------------------------------------------------------------


class MultiLanguageSearchEngine:
    """
    Singleton que gestiona un SingleLanguageEngine por cada lengua activa.

    Al iniciarse carga automáticamente los embeddings activos desde la BD.
    Se puede recargar una lengua específica sin afectar a las demás.
    """

    _instance: Optional['MultiLanguageSearchEngine'] = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._engines: Dict[str, SingleLanguageEngine] = {}
                    cls._instance._engines_lock = threading.Lock()
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'MultiLanguageSearchEngine':
        inst = cls()
        if not inst._initialized:
            inst._initialize()
        return inst

    def _initialize(self):
        with self._engines_lock:
            if self._initialized:
                return
            self._load_from_db()
            self._initialized = True

    def _load_from_db(self):
        """Carga todos los embeddings activos registrados en la BD."""
        try:
            from terminos.models import EmbeddingVersion
            active = EmbeddingVersion.objects.filter(status=EmbeddingVersion.STATUS_ACTIVE).select_related('lengua')
            for ev in active:
                self._engines[ev.lengua.codigo] = SingleLanguageEngine(
                    faiss_path=ev.faiss_path,
                    metadata_path=ev.metadata_path,
                    model_name=ev.model_name,
                )
            logger.info('MultiLanguageSearchEngine: %d lenguas cargadas desde BD', len(self._engines))
        except Exception as exc:
            logger.warning('No se pudieron cargar embeddings desde BD: %s', exc)

    def reload_language(self, codigo: str, faiss_path: str, metadata_path: str, model_name: str):
        """
        Reemplaza el motor de una lengua en caliente.
        El motor anterior se descarta; el nuevo carga en el primer uso (lazy).
        """
        new_engine = SingleLanguageEngine(
            faiss_path=faiss_path,
            metadata_path=metadata_path,
            model_name=model_name,
        )
        with self._engines_lock:
            self._engines[codigo] = new_engine
        logger.info('Motor recargado para lengua: %s', codigo)

    def search(self, query_text: str, language_code: str, top_k: int = 5) -> List[Dict]:
        engine = self._get_engine(language_code)
        if engine is None:
            raise ValueError(
                f'No hay un embedding activo para la lengua "{language_code}". '
                'Genera y activa un embedding primero.'
            )
        return engine.search(query_text, top_k=top_k)

    def _get_engine(self, language_code: str) -> Optional[SingleLanguageEngine]:
        with self._engines_lock:
            return self._engines.get(language_code)

    def available_languages(self) -> List[str]:
        with self._engines_lock:
            return list(self._engines.keys())


# ---------------------------------------------------------------------------
# API legacy — compatibilidad con translator_api.views existente
# ---------------------------------------------------------------------------

_LEGACY_MODEL_NAME = 'intfloat/multilingual-e5-base'
_legacy_engine: Optional[SingleLanguageEngine] = None
_legacy_lock = threading.Lock()


def _get_legacy_engine() -> SingleLanguageEngine:
    global _legacy_engine
    if _legacy_engine is not None:
        return _legacy_engine
    with _legacy_lock:
        if _legacy_engine is not None:
            return _legacy_engine
        base_dir = getattr(settings, 'ETTE_EMBEDDINGS_DIR', None)
        if not base_dir:
            raise RuntimeError('ETTE_EMBEDDINGS_DIR no está configurado en settings.py')
        base_dir = Path(base_dir)
        _legacy_engine = SingleLanguageEngine(
            faiss_path=str(base_dir / 'faiss_index.bin'),
            metadata_path=str(base_dir / 'metadata.json'),
            model_name=_LEGACY_MODEL_NAME,
        )
    return _legacy_engine


@lru_cache(maxsize=1)
def load_metadata() -> List[Dict]:
    """Compatibilidad con código existente que importa load_metadata()."""
    engine = _get_legacy_engine()
    engine._ensure_loaded()
    return engine._metadata


@lru_cache(maxsize=256)
def semantic_search(query_text: str, top_k: int = 5) -> List[Dict]:
    """Compatibilidad con código existente que llama semantic_search()."""
    return _get_legacy_engine().search(query_text, top_k=top_k)
