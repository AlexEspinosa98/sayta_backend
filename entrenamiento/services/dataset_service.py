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


def _session_stats(session_dir: Path) -> Dict:
    """Stats de una sola jornada."""
    audios_dir = session_dir / 'audios_sin_procesar'
    procesados_dir = session_dir / 'audios_procesados'
    total = 0
    etiquetados = 0
    if audios_dir.exists():
        for f in audios_dir.iterdir():
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
                total += 1
                if (procesados_dir / f'{f.stem}.txt').exists():
                    etiquetados += 1
    return {
        'total_audios': total,
        'etiquetados': etiquetados,
        'sin_etiquetar': total - etiquetados,
        'porcentaje': round(etiquetados / total * 100, 1) if total > 0 else 0.0,
    }


def _iter_labeled_samples(session_dir: Path) -> List[Dict]:
    """Pares {audio, sentence} de una sola jornada."""
    audios_dir = session_dir / 'audios_sin_procesar'
    procesados_dir = session_dir / 'audios_procesados'
    samples = []
    if not audios_dir.exists():
        return samples
    for audio_file in sorted(audios_dir.iterdir()):
        if not audio_file.is_file() or audio_file.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        txt_path = procesados_dir / f'{audio_file.stem}.txt'
        if txt_path.exists():
            transcript = txt_path.read_text(encoding='utf-8').strip()
            if transcript:
                samples.append({'audio': str(audio_file), 'sentence': transcript})
    return samples


# ------------------------------------------------------------------
# Endpoints de exploración
# ------------------------------------------------------------------

def get_dataset_stats() -> Dict:
    """Resumen por comunidad (nivel 1)."""
    base = _grabaciones_base()
    if not base.exists():
        return {
            'base_path': str(base),
            'existe': False,
            'comunidades': [],
            'advertencia': 'Directorio de grabaciones no encontrado.',
        }

    comunidades = []
    total_global = 0
    etiquetados_global = 0

    for community_dir in sorted(base.iterdir()):
        if not community_dir.is_dir():
            continue
        total = 0
        etiquetados = 0
        jornadas = 0
        for session_dir in sorted(community_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            s = _session_stats(session_dir)
            if s['total_audios'] == 0:
                continue
            jornadas += 1
            total += s['total_audios']
            etiquetados += s['etiquetados']

        total_global += total
        etiquetados_global += etiquetados
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
        'resumen_global': {
            'total_audios': total_global,
            'etiquetados': etiquetados_global,
            'sin_etiquetar': total_global - etiquetados_global,
            'porcentaje_completado': round(etiquetados_global / total_global * 100, 1) if total_global > 0 else 0.0,
        },
        'comunidades': comunidades,
    }


def get_community_stats(community_name: str) -> Optional[Dict]:
    """Estadísticas detalladas por jornada para una comunidad (nivel 2)."""
    base = _grabaciones_base()
    community_dir = next(
        (d for d in base.iterdir() if d.is_dir() and d.name.lower() == community_name.lower()),
        None,
    )
    if community_dir is None:
        return None

    jornadas = []
    for session_dir in sorted(community_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        s = _session_stats(session_dir)
        if s['total_audios'] == 0:
            continue
        jornadas.append({
            'comunidad': community_dir.name,
            'jornada': session_dir.name,
            **s,
            'apta': s['etiquetados'] > 0,
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


def get_all_sessions() -> Dict:
    """
    Lista plana de TODAS las jornadas de TODAS las comunidades.
    Usada por el frontend para mostrar checkboxes granulares de selección.
    """
    base = _grabaciones_base()
    if not base.exists():
        return {'existe': False, 'total_sesiones': 0, 'total_etiquetados': 0, 'sesiones': []}

    sesiones = []
    for community_dir in sorted(base.iterdir()):
        if not community_dir.is_dir():
            continue
        for session_dir in sorted(community_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            s = _session_stats(session_dir)
            if s['total_audios'] == 0:
                continue
            sesiones.append({
                'comunidad': community_dir.name,
                'jornada': session_dir.name,
                **s,
                'apta': s['etiquetados'] > 0,
            })

    total_etiquetados = sum(s['etiquetados'] for s in sesiones)
    return {
        'existe': True,
        'total_sesiones': len(sesiones),
        'total_etiquetados': total_etiquetados,
        'sesiones': sesiones,
    }


# ------------------------------------------------------------------
# Construcción de muestras para entrenamiento
# ------------------------------------------------------------------

def build_samples_from_sessions(sesiones: List[Dict]) -> List[Dict]:
    """
    Construye muestras desde jornadas específicas.
    sesiones: [{"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"}, ...]
    """
    base = _grabaciones_base()
    samples = []

    for item in sesiones:
        comunidad = item['comunidad']
        jornada = item['jornada']

        community_dir = next(
            (d for d in base.iterdir() if d.is_dir() and d.name.lower() == comunidad.lower()),
            None,
        )
        if community_dir is None:
            logger.warning('Comunidad "%s" no encontrada', comunidad)
            continue

        session_dir = community_dir / jornada
        if not session_dir.exists() or not session_dir.is_dir():
            logger.warning('Jornada "%s/%s" no encontrada', comunidad, jornada)
            continue

        session_samples = _iter_labeled_samples(session_dir)
        logger.info('Sesión %s/%s: %d muestras', comunidad, jornada, len(session_samples))
        samples.extend(session_samples)

    logger.info('Total muestras de %d sesiones: %d', len(sesiones), len(samples))
    return samples


def build_samples_from_communities(community_names: List[str]) -> List[Dict]:
    """Todas las jornadas etiquetadas de las comunidades indicadas."""
    base = _grabaciones_base()
    samples = []

    for name in community_names:
        community_dir = next(
            (d for d in base.iterdir() if d.is_dir() and d.name.lower() == name.lower()),
            None,
        )
        if community_dir is None:
            logger.warning('Comunidad "%s" no encontrada', name)
            continue
        for session_dir in sorted(community_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            session_samples = _iter_labeled_samples(session_dir)
            if session_samples:
                logger.info('  %s/%s: %d muestras', name, session_dir.name, len(session_samples))
                samples.extend(session_samples)

    logger.info('Total muestras (comunidades %s): %d', community_names, len(samples))
    return samples


def build_all_samples() -> List[Dict]:
    """Todos los audios etiquetados de TODAS las comunidades y jornadas."""
    base = _grabaciones_base()
    if not base.exists():
        return []

    samples = []
    for community_dir in sorted(base.iterdir()):
        if not community_dir.is_dir():
            continue
        for session_dir in sorted(community_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            session_samples = _iter_labeled_samples(session_dir)
            if session_samples:
                logger.info('  %s/%s: %d muestras', community_dir.name, session_dir.name, len(session_samples))
                samples.extend(session_samples)

    logger.info('Total global de muestras: %d', len(samples))
    return samples


# Alias para compatibilidad con código anterior
def build_samples(community_names: List[str]) -> List[Dict]:
    return build_samples_from_communities(community_names)


# ------------------------------------------------------------------
# Estadísticas de tiempo de grabación
# ------------------------------------------------------------------

def _audio_duration(path: Path) -> Optional[float]:
    """Retorna duración en segundos del archivo de audio, o None si falla."""
    try:
        import soundfile as sf
        return sf.info(str(path)).duration
    except Exception:
        pass
    try:
        import librosa
        return librosa.get_duration(path=str(path))
    except Exception:
        pass
    try:
        from mutagen import File as MutagenFile
        f = MutagenFile(str(path))
        if f is not None and f.info is not None:
            return f.info.length
    except Exception:
        pass
    return None


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    horas = total // 3600
    minutos = (total % 3600) // 60
    segs = total % 60
    if horas > 0:
        return f'{horas}h {minutos:02d}m {segs:02d}s'
    return f'{minutos}m {segs:02d}s'


def get_recording_time_stats() -> Dict:
    """
    Escanea todas las grabaciones y retorna estadísticas de tiempo y cantidad
    de archivos de audio por comunidad y en total.
    """
    base = _grabaciones_base()
    if not base.exists():
        return {
            'base_path': str(base),
            'existe': False,
            'advertencia': 'Directorio de grabaciones no encontrado.',
        }

    comunidades_data = []
    total_archivos_global = 0
    total_duracion_global = 0.0
    archivos_sin_duracion_global = 0

    for community_dir in sorted(base.iterdir()):
        if not community_dir.is_dir():
            continue

        jornadas_data = []
        total_archivos_comunidad = 0
        total_duracion_comunidad = 0.0
        archivos_sin_duracion_comunidad = 0

        for session_dir in sorted(community_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            audios_dir = session_dir / 'audios_sin_procesar'
            if not audios_dir.exists():
                continue

            archivos_jornada = 0
            duracion_jornada = 0.0
            sin_duracion_jornada = 0

            for f in sorted(audios_dir.iterdir()):
                if not f.is_file() or f.suffix.lower() not in AUDIO_EXTENSIONS:
                    continue
                archivos_jornada += 1
                dur = _audio_duration(f)
                if dur is not None:
                    duracion_jornada += dur
                else:
                    sin_duracion_jornada += 1

            if archivos_jornada == 0:
                continue

            jornadas_data.append({
                'jornada': session_dir.name,
                'total_archivos': archivos_jornada,
                'duracion_segundos': round(duracion_jornada, 2),
                'duracion_formateada': _format_duration(duracion_jornada),
                'archivos_sin_duracion': sin_duracion_jornada,
            })
            total_archivos_comunidad += archivos_jornada
            total_duracion_comunidad += duracion_jornada
            archivos_sin_duracion_comunidad += sin_duracion_jornada

        if total_archivos_comunidad == 0:
            continue

        comunidades_data.append({
            'comunidad': community_dir.name,
            'total_archivos': total_archivos_comunidad,
            'duracion_segundos': round(total_duracion_comunidad, 2),
            'duracion_formateada': _format_duration(total_duracion_comunidad),
            'archivos_sin_duracion': archivos_sin_duracion_comunidad,
            'jornadas': jornadas_data,
        })
        total_archivos_global += total_archivos_comunidad
        total_duracion_global += total_duracion_comunidad
        archivos_sin_duracion_global += archivos_sin_duracion_comunidad

    return {
        'base_path': str(base),
        'existe': True,
        'resumen_global': {
            'total_comunidades': len(comunidades_data),
            'total_archivos': total_archivos_global,
            'duracion_segundos': round(total_duracion_global, 2),
            'duracion_formateada': _format_duration(total_duracion_global),
            'archivos_sin_duracion': archivos_sin_duracion_global,
        },
        'por_comunidad': comunidades_data,
    }


# ------------------------------------------------------------------
# Subida de audios al dataset
# ------------------------------------------------------------------

def save_audio_sample(
    comunidad: str,
    jornada: str,
    audio_file,
    transcripcion: str,
) -> Dict:
    """
    Guarda un par (audio, transcripción) en la estructura de Grabaciones.
    Crea los directorios comunidad/jornada si no existen.
    Si ya existe un archivo con el mismo nombre añade sufijo de timestamp.

    Retorna un dict con rutas, duración y estadísticas actualizadas de la jornada.
    """
    from datetime import datetime
    from pathlib import Path as _Path

    base = _grabaciones_base()
    session_dir = base / comunidad / jornada
    audios_dir = session_dir / 'audios_sin_procesar'
    procesados_dir = session_dir / 'audios_procesados'

    audios_dir.mkdir(parents=True, exist_ok=True)
    procesados_dir.mkdir(parents=True, exist_ok=True)

    # Resolver nombre de archivo — evitar sobreescrituras
    original_name = _Path(audio_file.name).name
    stem = _Path(original_name).stem
    suffix = _Path(original_name).suffix.lower()
    audio_path = audios_dir / f'{stem}{suffix}'

    if audio_path.exists():
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        stem = f'{stem}_{ts}'
        audio_path = audios_dir / f'{stem}{suffix}'

    # Guardar audio
    with open(audio_path, 'wb') as fh:
        for chunk in audio_file.chunks():
            fh.write(chunk)

    # Guardar transcripción
    txt_path = procesados_dir / f'{stem}.txt'
    txt_path.write_text(transcripcion.strip(), encoding='utf-8')

    # Duración del audio (best-effort)
    duracion = None
    try:
        import soundfile as sf
        info = sf.info(str(audio_path))
        duracion = round(info.duration, 2)
    except Exception:
        try:
            import librosa
            duracion = round(librosa.get_duration(path=str(audio_path)), 2)
        except Exception:
            pass

    # Stats actualizadas de la jornada
    stats = _session_stats(session_dir)

    logger.info(
        'Audio guardado: %s/%s/%s (%.1f s)',
        comunidad, jornada, audio_path.name, duracion or 0,
    )

    return {
        'comunidad': comunidad,
        'jornada': jornada,
        'archivo_audio': audio_path.name,
        'transcripcion_guardada': transcripcion.strip(),
        'duracion_segundos': duracion,
        'ruta_relativa': f'Grabaciones/{comunidad}/{jornada}/audios_sin_procesar/{audio_path.name}',
        'jornada_stats': {
            'total_audios': stats['total_audios'],
            'etiquetados': stats['etiquetados'],
            'sin_etiquetar': stats['sin_etiquetar'],
            'porcentaje': stats['porcentaje'],
        },
    }
