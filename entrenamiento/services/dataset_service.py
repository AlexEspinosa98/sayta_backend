"""
Servicio de dataset: construye pares (audio, transcripción) desde las carpetas
de Grabaciones etiquetadas, listos para entrenamiento HuggingFace.

Estructura esperada en disco:
  Grabaciones/
    <comunidad>/
      <jornada>/
        audios_sin_procesar/  ← archivos de audio (.wav, .mp3, …)
        audios_procesados/    ← transcripciones .txt con el mismo stem
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.mp4', '.m4a', '.ogg', '.flac'}

MIN_MUESTRAS_ENTRENAMIENTO = 5


def _grabaciones_base() -> Path:
    base = Path(settings.BASE_DIR)
    for _ in range(4):
        base = base.parent
    return base / 'mnt' / 'sayta_data' / 'data' / 'Grabaciones'


def _iter_labeled_samples(community_dir: Path) -> List[Dict]:
    """Retorna lista de {audio, sentence} para todos los audios etiquetados de una comunidad."""
    samples = []
    for session_dir in sorted(community_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        audios_dir = session_dir / 'audios_sin_procesar'
        procesados_dir = session_dir / 'audios_procesados'
        if not audios_dir.exists():
            continue
        for audio_file in sorted(audios_dir.iterdir()):
            if not audio_file.is_file() or audio_file.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            txt_path = procesados_dir / f'{audio_file.stem}.txt'
            if txt_path.exists():
                transcript = txt_path.read_text(encoding='utf-8').strip()
                if transcript:
                    samples.append({'audio': str(audio_file), 'sentence': transcript})
    return samples


def get_dataset_stats() -> Dict:
    """Resumen de datos etiquetados disponibles por comunidad."""
    base = _grabaciones_base()
    if not base.exists():
        return {
            'base_path': str(base),
            'existe': False,
            'comunidades': [],
            'advertencia': 'Directorio de grabaciones no encontrado.',
        }

    comunidades = []
    for community_dir in sorted(base.iterdir()):
        if not community_dir.is_dir():
            continue

        total = 0
        etiquetados = 0
        jornadas = 0
        for session_dir in sorted(community_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            audios_dir = session_dir / 'audios_sin_procesar'
            procesados_dir = session_dir / 'audios_procesados'
            if not audios_dir.exists():
                continue
            jornadas += 1
            for f in audios_dir.iterdir():
                if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                    total += 1
                    if (procesados_dir / f'{f.stem}.txt').exists():
                        etiquetados += 1

        comunidades.append({
            'comunidad': community_dir.name,
            'total_jornadas': jornadas,
            'total_audios': total,
            'etiquetados': etiquetados,
            'sin_etiquetar': total - etiquetados,
            'porcentaje_completado': round(etiquetados / total * 100, 1) if total > 0 else 0.0,
            'apto_para_entrenamiento': etiquetados >= MIN_MUESTRAS_ENTRENAMIENTO,
        })

    return {
        'base_path': str(base),
        'existe': True,
        'total_comunidades': len(comunidades),
        'comunidades': comunidades,
    }


def get_community_stats(community_name: str) -> Optional[Dict]:
    """Estadísticas detalladas por jornada para una comunidad."""
    base = _grabaciones_base()
    community_dir = None
    for d in base.iterdir():
        if d.is_dir() and d.name.lower() == community_name.lower():
            community_dir = d
            break
    if community_dir is None:
        return None

    jornadas = []
    for session_dir in sorted(community_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        audios_dir = session_dir / 'audios_sin_procesar'
        procesados_dir = session_dir / 'audios_procesados'
        if not audios_dir.exists():
            continue
        total = 0
        etiquetados = 0
        for f in audios_dir.iterdir():
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                total += 1
                if (procesados_dir / f'{f.stem}.txt').exists():
                    etiquetados += 1
        jornadas.append({
            'jornada': session_dir.name,
            'total_audios': total,
            'etiquetados': etiquetados,
            'porcentaje': round(etiquetados / total * 100, 1) if total > 0 else 0.0,
        })

    total_etiquetados = sum(j['etiquetados'] for j in jornadas)
    total_audios = sum(j['total_audios'] for j in jornadas)

    return {
        'comunidad': community_dir.name,
        'total_audios': total_audios,
        'etiquetados': total_etiquetados,
        'apto_para_entrenamiento': total_etiquetados >= MIN_MUESTRAS_ENTRENAMIENTO,
        'jornadas': jornadas,
    }


def build_samples(community_names: List[str]) -> List[Dict]:
    """
    Construye lista de {audio, sentence} desde una o varias comunidades.
    Filtra audios que no se puedan cargar.
    """
    base = _grabaciones_base()
    samples = []

    for name in community_names:
        community_dir = None
        for d in base.iterdir():
            if d.is_dir() and d.name.lower() == name.lower():
                community_dir = d
                break
        if community_dir is None:
            logger.warning('Comunidad "%s" no encontrada en %s', name, base)
            continue
        community_samples = _iter_labeled_samples(community_dir)
        logger.info('Comunidad "%s": %d muestras etiquetadas', name, len(community_samples))
        samples.extend(community_samples)

    logger.info('Total muestras para entrenamiento: %d', len(samples))
    return samples
