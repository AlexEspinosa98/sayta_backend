"""
Servicio de generación de embeddings por lengua.

Usa threading para no bloquear el backend: el endpoint retorna inmediatamente
con un task_id y la generación ocurre en segundo plano actualizando el estado
en base de datos.

Diagrama de estados de EmbeddingVersion:
  pending → generating → ready ←→ active
                       └→ failed
"""

import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Registro en memoria de hilos activos (solo informativo, no crítico)
_active_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


class EmbeddingService:
    """
    Singleton que gestiona la generación asíncrona de embeddings y su activación.

    Cada lengua puede tener múltiples versiones de embeddings, pero solo
    una puede estar activa a la vez. Al activar una versión, el motor de
    búsqueda multi-lengua se recarga automáticamente.
    """

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    # ------------------------------------------------------------------
    # Propiedades de configuración
    # ------------------------------------------------------------------

    @property
    def storage_dir(self) -> Path:
        base = getattr(settings, 'EMBEDDINGS_STORAGE_DIR', None)
        if not base:
            raise RuntimeError('EMBEDDINGS_STORAGE_DIR no está configurado en settings.py')
        path = Path(base)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def default_model(self) -> str:
        return getattr(settings, 'EMBEDDING_MODEL', 'intfloat/multilingual-e5-base')

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def generar(self, lengua_id: int, model_name: str | None = None) -> str:
        """
        Dispara la generación asíncrona de embeddings para una lengua.
        Retorna el task_id de la EmbeddingVersion creada.
        """
        from terminos.models import EmbeddingVersion, Lengua

        lengua = Lengua.objects.get(pk=lengua_id)
        model_name = model_name or self.default_model
        version_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_id = str(uuid.uuid4())

        ev = EmbeddingVersion.objects.create(
            lengua=lengua,
            version=version_str,
            model_name=model_name,
            status=EmbeddingVersion.STATUS_PENDING,
            task_id=task_id,
        )

        hilo = threading.Thread(
            target=self._run_generation,
            args=(str(ev.id),),
            daemon=True,
            name=f'emb_{lengua.codigo}_{task_id[:8]}',
        )

        with _tasks_lock:
            _active_tasks[task_id] = {
                'embedding_version_id': str(ev.id),
                'lengua': lengua.codigo,
                'started_at': datetime.now().isoformat(),
            }

        hilo.start()
        logger.info('Generación de embeddings iniciada: lengua=%s task_id=%s', lengua.codigo, task_id)
        return task_id

    def activar(self, embedding_version_id: str) -> 'EmbeddingVersion':
        """
        Activa una versión de embedding y recarga el motor de búsqueda.
        Desactiva automáticamente la versión que estuviera activa para esa lengua.
        """
        from django.db import transaction

        from terminos.models import EmbeddingVersion

        with transaction.atomic():
            ev = EmbeddingVersion.objects.select_for_update().get(pk=embedding_version_id)

            if ev.status not in (EmbeddingVersion.STATUS_READY, EmbeddingVersion.STATUS_ACTIVE):
                raise ValueError(
                    f'No se puede activar un embedding con estado "{ev.status}". '
                    'Debe estar en estado "ready" o "active".'
                )

            # Desactivar versión activa anterior de la misma lengua
            EmbeddingVersion.objects.filter(
                lengua=ev.lengua,
                status=EmbeddingVersion.STATUS_ACTIVE,
            ).update(status=EmbeddingVersion.STATUS_READY, is_active=False)

            ev.status = EmbeddingVersion.STATUS_ACTIVE
            ev.is_active = True
            ev.save(update_fields=['status', 'is_active'])

        # Recargar motor de búsqueda para esta lengua
        self._recargar_motor(ev)

        logger.info(
            'Embedding activado: lengua=%s version=%s id=%s',
            ev.lengua.codigo, ev.version, ev.id,
        )
        return ev

    def get_task_info(self, task_id: str) -> dict | None:
        with _tasks_lock:
            return _active_tasks.get(task_id)

    # ------------------------------------------------------------------
    # Tarea background
    # ------------------------------------------------------------------

    def _run_generation(self, embedding_version_id: str) -> None:
        """Ejecuta la generación de embeddings en un hilo separado."""
        from terminos.models import EmbeddingVersion, TerminoLeng

        ev = None
        try:
            ev = EmbeddingVersion.objects.get(pk=embedding_version_id)
            ev.status = EmbeddingVersion.STATUS_GENERATING
            ev.save(update_fields=['status'])

            terminos_qs = TerminoLeng.objects.filter(
                lengua=ev.lengua, activo=True
            ).select_related('termino_es').values(
                'termino', 'definicion', 'pos', 'sinonimos', 'ejemplos',
                'tipo_morfema', 'termino_es__termino',
            )

            terminos = list(terminos_qs)

            if not terminos:
                raise ValueError('No hay términos activos para esta lengua')

            corpus, metadata = self._construir_corpus(terminos)
            embeddings, index = self._generar_vectores(corpus, ev.model_name)
            paths = self._guardar_artefactos(ev, embeddings, index, metadata)

            ev.status = EmbeddingVersion.STATUS_READY
            ev.num_terminos = len(terminos)
            ev.embeddings_path = paths['embeddings']
            ev.faiss_path = paths['faiss']
            ev.metadata_path = paths['metadata']
            ev.completed_at = timezone.now()
            ev.error_message = ''
            ev.save()

            logger.info(
                'Embeddings generados OK: lengua=%s version=%s terminos=%d',
                ev.lengua.codigo, ev.version, len(terminos),
            )

        except Exception as exc:
            logger.error('Error generando embeddings id=%s: %s', embedding_version_id, exc, exc_info=True)
            if ev is not None:
                try:
                    ev.status = EmbeddingVersion.STATUS_FAILED
                    ev.error_message = str(exc)
                    ev.completed_at = timezone.now()
                    ev.save(update_fields=['status', 'error_message', 'completed_at'])
                except Exception:
                    pass
        finally:
            with _tasks_lock:
                _active_tasks.pop(ev.task_id if ev else '', None)
            # Liberar la conexión DB del hilo; Django no lo hace automáticamente en threads
            try:
                from django.db import connection
                connection.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _construir_corpus(terminos: list[dict]) -> tuple[list[str], list[dict]]:
        corpus = []
        metadata = []
        for t in terminos:
            texto = f"passage: {t['termino']}"
            if t['definicion']:
                texto += f" {t['definicion']}"
            corpus.append(texto)
            metadata.append({
                'lemma': t['termino'],
                'termino_es': t.get('termino_es__termino') or '',
                'definicion': t['definicion'],
                'pos': t['pos'],
                'sinonimos': t['sinonimos'],
                'ejemplos': t['ejemplos'],
                'tipo_morfema': t['tipo_morfema'],
            })
        return corpus, metadata

    @staticmethod
    def _generar_vectores(corpus: list[str], model_name: str):
        """Genera embeddings y construye el índice FAISS HNSW."""
        import numpy as np

        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("Dependencia 'faiss-cpu' no instalada") from exc

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Dependencia 'sentence-transformers' no instalada") from exc

        model = SentenceTransformer(model_name)
        embeddings = model.encode(
            corpus, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )

        dim = embeddings.shape[1]
        index = faiss.IndexHNSWFlat(dim, 32)
        index.hnsw.efConstruction = 200
        index.hnsw.efSearch = 64
        index.add(embeddings.astype('float32'))

        return embeddings, index

    def _guardar_artefactos(self, ev, embeddings, index, metadata: list[dict]) -> dict:
        """Persiste los artefactos en disco y retorna las rutas absolutas."""
        import faiss
        import numpy as np

        output_dir: Path = self.storage_dir / ev.lengua.codigo / ev.version
        output_dir.mkdir(parents=True, exist_ok=True)

        embeddings_path = str(output_dir / 'embeddings.npy')
        faiss_path = str(output_dir / 'faiss_index.bin')
        metadata_path = str(output_dir / 'metadata.json')

        np.save(embeddings_path, embeddings)
        faiss.write_index(index, faiss_path)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        return {'embeddings': embeddings_path, 'faiss': faiss_path, 'metadata': metadata_path}

    @staticmethod
    def _recargar_motor(ev) -> None:
        """Recarga el motor de búsqueda multi-lengua con la nueva versión activa."""
        try:
            from translator_api.search_engine import MultiLanguageSearchEngine
            engine = MultiLanguageSearchEngine.get_instance()
            engine.reload_language(
                codigo=ev.lengua.codigo,
                faiss_path=ev.faiss_path,
                metadata_path=ev.metadata_path,
                model_name=ev.model_name,
            )
        except Exception as exc:
            logger.warning('No se pudo recargar motor de búsqueda: %s', exc)
