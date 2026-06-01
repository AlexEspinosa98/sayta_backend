"""
Gestión de modelos HuggingFace para ASR:
- Catálogo de modelos abiertos recomendados
- Descarga y almacenamiento local
- Carga en memoria (con caché por lengua activa)
"""

import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Catálogo de modelos disponibles
# ------------------------------------------------------------------

CATALOGO = [
    {
        'nombre_hf': 'openai/whisper-small',
        'tipo': 'whisper',
        'descripcion': (
            'Whisper Small — 244M parámetros. Multilingüe, excelente para fine-tuning '
            'en lenguas indígenas. Balance ideal rendimiento/tamaño. Recomendado.'
        ),
        'tamaño_aprox': '461 MB',
        'parametros': '244M',
        'recomendado': True,
        'gpu_requerida': False,
    },
    {
        'nombre_hf': 'openai/whisper-tiny',
        'tipo': 'whisper',
        'descripcion': (
            'Whisper Tiny — 39M parámetros. El más ligero; adecuado para hardware '
            'sin GPU o pruebas rápidas con pocos datos.'
        ),
        'tamaño_aprox': '151 MB',
        'parametros': '39M',
        'recomendado': False,
        'gpu_requerida': False,
    },
    {
        'nombre_hf': 'openai/whisper-medium',
        'tipo': 'whisper',
        'descripcion': (
            'Whisper Medium — 769M parámetros. Mayor precisión, requiere más VRAM. '
            'Ideal si tienes GPU con 8GB+ y suficientes muestras etiquetadas.'
        ),
        'tamaño_aprox': '1.5 GB',
        'parametros': '769M',
        'recomendado': False,
        'gpu_requerida': True,
    },
    {
        'nombre_hf': 'facebook/wav2vec2-large-xlsr-53',
        'tipo': 'wav2vec2',
        'descripcion': (
            'Wav2Vec2 XLSR-53 — 315M parámetros. Pre-entrenado en 53 idiomas con CTC. '
            'Muy adecuado para fine-tuning en lenguas con pocos recursos. Recomendado.'
        ),
        'tamaño_aprox': '1.2 GB',
        'parametros': '315M',
        'recomendado': True,
        'gpu_requerida': False,
    },
    {
        'nombre_hf': 'facebook/wav2vec2-base',
        'tipo': 'wav2vec2',
        'descripcion': (
            'Wav2Vec2 Base — 95M parámetros. Más pequeño, solo inglés pre-entrenado. '
            'Útil para pruebas de pipeline o datasets muy pequeños (<50 muestras).'
        ),
        'tamaño_aprox': '370 MB',
        'parametros': '95M',
        'recomendado': False,
        'gpu_requerida': False,
    },
]


def _models_dir() -> Path:
    path = Path(getattr(settings, 'AUDIO_MODELS_DIR', str(Path(settings.BASE_DIR) / 'audio_models')))
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_path_for(nombre_hf: str) -> Path:
    return _models_dir() / nombre_hf.replace('/', '__')


def is_downloaded(nombre_hf: str) -> bool:
    p = local_path_for(nombre_hf)
    return p.exists() and any(p.iterdir())


def download_model(nombre_hf: str, tipo: str) -> Dict:
    """
    Descarga un modelo y su procesador desde HuggingFace Hub al disco local.
    Retorna {success, ruta_local, mensaje/error}.
    """
    try:
        from transformers import (
            Wav2Vec2FeatureExtractor,
            Wav2Vec2ForCTC,
            WhisperForConditionalGeneration,
            WhisperProcessor,
        )
    except ImportError:
        return {'success': False, 'error': 'transformers no instalado.'}

    local_path = local_path_for(nombre_hf)
    local_path.mkdir(parents=True, exist_ok=True)

    logger.info('Descargando %s → %s', nombre_hf, local_path)
    try:
        if tipo == 'whisper':
            processor = WhisperProcessor.from_pretrained(nombre_hf)
            model = WhisperForConditionalGeneration.from_pretrained(nombre_hf)
        else:
            feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(nombre_hf)
            model = Wav2Vec2ForCTC.from_pretrained(nombre_hf)
            feature_extractor.save_pretrained(str(local_path))
            model.save_pretrained(str(local_path))
            return {
                'success': True,
                'ruta_local': str(local_path),
                'mensaje': f'{nombre_hf} descargado correctamente.',
            }

        processor.save_pretrained(str(local_path))
        model.save_pretrained(str(local_path))
        return {
            'success': True,
            'ruta_local': str(local_path),
            'mensaje': f'{nombre_hf} descargado correctamente.',
        }
    except Exception as exc:
        logger.error('Error descargando %s: %s', nombre_hf, exc)
        return {'success': False, 'error': str(exc)}


# ------------------------------------------------------------------
# Caché de modelos cargados en memoria
# ------------------------------------------------------------------

_loaded_models: Dict[str, Tuple] = {}   # key → (model, processor)
_cache_lock = threading.Lock()


def load_asr_model(ruta_local: str, tipo: str) -> Tuple:
    """
    Carga modelo y procesador desde disco con caché.
    Retorna (model, processor).
    """
    with _cache_lock:
        if ruta_local in _loaded_models:
            return _loaded_models[ruta_local]

    try:
        if tipo == 'whisper':
            from transformers import WhisperForConditionalGeneration, WhisperProcessor
            processor = WhisperProcessor.from_pretrained(ruta_local)
            model = WhisperForConditionalGeneration.from_pretrained(ruta_local)
        else:
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
            processor = Wav2Vec2Processor.from_pretrained(ruta_local)
            model = Wav2Vec2ForCTC.from_pretrained(ruta_local)

        model.eval()
        with _cache_lock:
            _loaded_models[ruta_local] = (model, processor)
        logger.info('Modelo ASR cargado desde %s', ruta_local)
        return model, processor
    except Exception as exc:
        raise RuntimeError(f'No se pudo cargar el modelo desde {ruta_local}: {exc}') from exc


def invalidate_cache(ruta_local: str) -> None:
    with _cache_lock:
        _loaded_models.pop(ruta_local, None)


def transcribe_audio(audio_path: str, model, processor, tipo: str, language: str = 'es') -> str:
    """
    Transcribe un archivo de audio usando el modelo y procesador dados.
    Retorna el texto transcrito.
    """
    import torch

    try:
        import librosa
        speech, _ = librosa.load(audio_path, sr=16000, mono=True)
    except Exception as exc:
        raise RuntimeError(f'No se pudo cargar el audio {audio_path}: {exc}') from exc

    if tipo == 'whisper':
        input_features = processor(speech, sampling_rate=16000, return_tensors='pt').input_features
        with torch.no_grad():
            predicted_ids = model.generate(
                input_features,
                language=language,
                task='transcribe',
            )
        return processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()

    else:  # wav2vec2
        inputs = processor(speech, sampling_rate=16000, return_tensors='pt', padding=True)
        with torch.no_grad():
            logits = model(inputs.input_values).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        return processor.batch_decode(predicted_ids)[0].strip()
