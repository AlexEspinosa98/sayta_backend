"""
Servicio de Data Augmentation para audio (ASR).

Las técnicas generan NUEVAS muestras a partir de las existentes —
no reemplazan ni modifican los archivos originales. Cada muestra
aumentada hereda la misma transcripción del original.

Los archivos generados se cachean en output_dir:
si el archivo ya existe no se regenera (útil en K-Fold, donde el
mismo audio puede ser procesado en múltiples folds).

Uso desde training_service:
    from entrenamiento.services import augmentation_service
    samples = augmentation_service.aplicar_augmentation(samples, config['augmentation'], aug_dir)
"""

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Catálogo público ───────────────────────────────────────────────────────
# Usado por GET /api/entrenamiento/dataset/augmentation/ y por la validación.

CATALOGO: Dict[str, Dict] = {
    'ruido_gaussiano': {
        'nombre': 'Ruido Gaussiano',
        'descripcion': (
            'Añade ruido blanco gaussiano al audio. Simula grabaciones en entornos '
            'con ruido ambiental (viento, vegetación, voces lejanas). '
            'Ideal para mejorar la robustez en grabaciones de campo.'
        ),
        'parametros': {
            'intensidad': {
                'tipo': 'float',
                'min': 0.001,
                'max': 0.05,
                'default': 0.005,
                'descripcion': (
                    'Amplitud del ruido relativa a la señal. '
                    '0.002 = casi imperceptible, 0.01 = sutil, 0.03 = notable.'
                ),
            },
        },
        'porcentaje_default': 30,
        'recomendado': True,
        'impacto_tiempo': 'bajo',
        'requiere_gpu': False,
    },
    'cambio_velocidad': {
        'nombre': 'Cambio de Velocidad (Time Stretching)',
        'descripcion': (
            'Acelera o ralentiza el habla sin modificar el tono. '
            'Simula variaciones naturales en la velocidad del hablante '
            'y mejora la robustez ante diferentes cadencias de habla.'
        ),
        'parametros': {
            'factor_min': {
                'tipo': 'float',
                'min': 0.7,
                'max': 1.0,
                'default': 0.9,
                'descripcion': 'Factor mínimo de velocidad (0.9 = 10 % más lento que el original).',
            },
            'factor_max': {
                'tipo': 'float',
                'min': 1.0,
                'max': 1.3,
                'default': 1.1,
                'descripcion': 'Factor máximo de velocidad (1.1 = 10 % más rápido que el original).',
            },
        },
        'porcentaje_default': 20,
        'recomendado': True,
        'impacto_tiempo': 'medio',
        'requiere_gpu': False,
    },
    'cambio_tono': {
        'nombre': 'Cambio de Tono (Pitch Shifting)',
        'descripcion': (
            'Modifica el tono de la voz sin cambiar la velocidad. '
            'Simula diferentes tipos de hablantes (voces graves/agudas, '
            'hombres, mujeres, niños) sin necesitar más grabaciones reales.'
        ),
        'parametros': {
            'semitonos_min': {
                'tipo': 'int',
                'min': -6,
                'max': 0,
                'default': -2,
                'descripcion': 'Semitonos mínimos a desplazar (negativo = más grave). Ej: -2.',
            },
            'semitonos_max': {
                'tipo': 'int',
                'min': 0,
                'max': 6,
                'default': 2,
                'descripcion': 'Semitonos máximos a desplazar (positivo = más agudo). Ej: 2.',
            },
        },
        'porcentaje_default': 20,
        'recomendado': True,
        'impacto_tiempo': 'alto',
        'requiere_gpu': False,
    },
    'reduccion_volumen': {
        'nombre': 'Reducción de Volumen',
        'descripcion': (
            'Reduce aleatoriamente la ganancia del audio. '
            'Simula grabaciones con micrófono a mayor distancia, '
            'batería descargada o condiciones de campo adversas.'
        ),
        'parametros': {
            'factor_min': {
                'tipo': 'float',
                'min': 0.2,
                'max': 0.8,
                'default': 0.5,
                'descripcion': 'Factor mínimo de ganancia (0.5 = 50 % del volumen original).',
            },
            'factor_max': {
                'tipo': 'float',
                'min': 0.6,
                'max': 1.0,
                'default': 0.9,
                'descripcion': 'Factor máximo de ganancia (0.9 = 90 % del volumen original).',
            },
        },
        'porcentaje_default': 20,
        'recomendado': True,
        'impacto_tiempo': 'bajo',
        'requiere_gpu': False,
    },
    'recorte_tiempo': {
        'nombre': 'Enmascaramiento Temporal (Time Masking)',
        'descripcion': (
            'Silencia un segmento aleatorio del audio. '
            'Técnica de regularización (inspirada en SpecAugment) que evita que el modelo '
            'dependa de fragmentos específicos del audio y mejora la generalización.'
        ),
        'parametros': {
            'max_porcentaje_clip': {
                'tipo': 'int',
                'min': 5,
                'max': 30,
                'default': 10,
                'descripcion': (
                    'Porcentaje máximo del audio total a silenciar. '
                    '10 = el segmento silenciado puede ser hasta el 10 % de la duración.'
                ),
            },
        },
        'porcentaje_default': 15,
        'recomendado': False,
        'impacto_tiempo': 'bajo',
        'requiere_gpu': False,
    },
    'eco': {
        'nombre': 'Eco / Reverberación Simple',
        'descripcion': (
            'Superpone una copia retrasada y atenuada de la señal (eco). '
            'Simula grabaciones en espacios con reverberación natural: '
            'maloca, aula, espacio techado, cueva.'
        ),
        'parametros': {
            'delay_ms': {
                'tipo': 'int',
                'min': 10,
                'max': 200,
                'default': 50,
                'descripcion': 'Retardo del eco en milisegundos. 30–80 ms = sala pequeña, 100–200 ms = espacio grande.',
            },
            'decay': {
                'tipo': 'float',
                'min': 0.05,
                'max': 0.5,
                'default': 0.2,
                'descripcion': 'Amplitud del eco relativa a la señal original (0.2 = 20 % de la señal).',
            },
        },
        'porcentaje_default': 10,
        'recomendado': False,
        'impacto_tiempo': 'bajo',
        'requiere_gpu': False,
    },
}


def get_catalogo_completo() -> Dict:
    """Devuelve el catálogo con config ejemplo lista para copiar en POST /entrenar/."""
    resultado = {}
    for nombre, info in CATALOGO.items():
        resultado[nombre] = {
            **info,
            'config_ejemplo': {
                'habilitado': True,
                'porcentaje': info['porcentaje_default'],
                **{k: v['default'] for k, v in info['parametros'].items()},
            },
        }
    return resultado


# ── Punto de entrada público ───────────────────────────────────────────────

def aplicar_augmentation(
    samples: List[Dict],
    aug_config: Dict,
    output_dir: Path,
) -> List[Dict]:
    """
    Aplica las técnicas habilitadas a un subconjunto aleatorio de samples.

    Retorna samples originales + nuevas muestras aumentadas.
    Los archivos se guardan en output_dir con nombres deterministas;
    si ya existen (cache hit en K-Fold) se omite la regeneración.

    Args:
        samples:    Lista de {'audio': str, 'sentence': str}.
        aug_config: Dict con 'habilitado' y 'tecnicas'.
        output_dir: Directorio donde guardar los archivos generados.

    Returns:
        Lista expandida de samples (originales + aumentados).
    """
    if not aug_config.get('habilitado', False):
        return list(samples)

    tecnicas_config = aug_config.get('tecnicas') or {}
    if not tecnicas_config:
        logger.info('Data augmentation habilitado pero sin técnicas activas, omitido.')
        return list(samples)

    try:
        import numpy as np  # noqa: F401
    except ImportError:
        logger.error('numpy no disponible — augmentation omitido.')
        return list(samples)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    nuevas: List[Dict] = []
    tecnicas_ejecutadas: List[str] = []

    for nombre_tecnica, tc_config in tecnicas_config.items():
        if not isinstance(tc_config, dict):
            continue
        if not tc_config.get('habilitado', False):
            continue
        if nombre_tecnica not in CATALOGO:
            logger.warning('Técnica de augmentation desconocida ignorada: "%s"', nombre_tecnica)
            continue

        porcentaje = float(tc_config.get('porcentaje', CATALOGO[nombre_tecnica]['porcentaje_default']))
        porcentaje = max(1.0, min(100.0, porcentaje))

        n_objetivo = max(1, round(len(samples) * porcentaje / 100))
        seleccionados = random.sample(samples, min(n_objetivo, len(samples)))

        fn = _TECNICAS.get(nombre_tecnica)
        if fn is None:
            logger.warning('Función de augmentation no implementada: %s', nombre_tecnica)
            continue

        generados = 0
        errores = 0
        for sample in seleccionados:
            try:
                resultado = fn(sample, tc_config, output_dir)
                if resultado:
                    nuevas.append(resultado)
                    generados += 1
            except Exception as exc:
                logger.debug(
                    'Augmentation [%s] falló en "%s": %s',
                    nombre_tecnica, Path(sample['audio']).name, exc,
                )
                errores += 1

        tecnicas_ejecutadas.append(nombre_tecnica)
        logger.info(
            'Augmentation [%s]: seleccionadas %d/%d muestras (%.0f %%) → %d generadas, %d errores',
            nombre_tecnica, len(seleccionados), len(samples), porcentaje, generados, errores,
        )

    if nuevas:
        logger.info(
            'Data augmentation completa: %d originales + %d aumentadas = %d total | técnicas: %s',
            len(samples), len(nuevas), len(samples) + len(nuevas),
            ', '.join(tecnicas_ejecutadas),
        )

    return list(samples) + nuevas


# ── Helpers internos ───────────────────────────────────────────────────────

def _load_audio(path: str):
    import librosa
    return librosa.load(path, sr=16000, mono=True)  # (speech_array, sr)


def _save_audio(speech, output_path: Path) -> None:
    """Guarda en disco solo si no existe (caché)."""
    if output_path.exists():
        return
    import soundfile as sf
    sf.write(str(output_path), speech, 16000)


def _aug_path(sample: Dict, tecnica: str, output_dir: Path) -> Path:
    """Nombre determinista: <stem>__<tecnica>.wav"""
    stem = Path(sample['audio']).stem
    return output_dir / f'{stem}__{tecnica}.wav'


# ── Implementación de técnicas ─────────────────────────────────────────────

def _aug_ruido_gaussiano(
    sample: Dict, config: Dict, output_dir: Path
) -> Optional[Dict]:
    import numpy as np
    out_path = _aug_path(sample, 'ruido', output_dir)
    if not out_path.exists():
        intensidad = float(config.get('intensidad', 0.005))
        speech, _ = _load_audio(sample['audio'])
        ruido = np.random.normal(0.0, intensidad, len(speech)).astype(np.float32)
        aumentado = np.clip(speech + ruido, -1.0, 1.0).astype(np.float32)
        _save_audio(aumentado, out_path)
    return {'audio': str(out_path), 'sentence': sample['sentence']}


def _aug_cambio_velocidad(
    sample: Dict, config: Dict, output_dir: Path
) -> Optional[Dict]:
    import librosa
    import numpy as np
    out_path = _aug_path(sample, 'velocidad', output_dir)
    if not out_path.exists():
        factor_min = float(config.get('factor_min', 0.9))
        factor_max = float(config.get('factor_max', 1.1))
        rate = random.uniform(factor_min, factor_max)
        speech, _ = _load_audio(sample['audio'])
        aumentado = librosa.effects.time_stretch(speech, rate=rate)
        _save_audio(aumentado.astype(np.float32), out_path)
    return {'audio': str(out_path), 'sentence': sample['sentence']}


def _aug_cambio_tono(
    sample: Dict, config: Dict, output_dir: Path
) -> Optional[Dict]:
    import librosa
    import numpy as np
    out_path = _aug_path(sample, 'tono', output_dir)
    if not out_path.exists():
        semitonos_min = float(config.get('semitonos_min', -2))
        semitonos_max = float(config.get('semitonos_max', 2))
        n_steps = random.uniform(semitonos_min, semitonos_max)
        if abs(n_steps) < 0.1:
            n_steps = 1.0  # evitar transformación nula
        speech, _ = _load_audio(sample['audio'])
        aumentado = librosa.effects.pitch_shift(speech, sr=16000, n_steps=n_steps)
        _save_audio(aumentado.astype(np.float32), out_path)
    return {'audio': str(out_path), 'sentence': sample['sentence']}


def _aug_reduccion_volumen(
    sample: Dict, config: Dict, output_dir: Path
) -> Optional[Dict]:
    import numpy as np
    out_path = _aug_path(sample, 'volumen', output_dir)
    if not out_path.exists():
        factor_min = float(config.get('factor_min', 0.5))
        factor_max = float(config.get('factor_max', 0.9))
        factor = random.uniform(factor_min, factor_max)
        speech, _ = _load_audio(sample['audio'])
        _save_audio((speech * factor).astype(np.float32), out_path)
    return {'audio': str(out_path), 'sentence': sample['sentence']}


def _aug_recorte_tiempo(
    sample: Dict, config: Dict, output_dir: Path
) -> Optional[Dict]:
    import numpy as np
    out_path = _aug_path(sample, 'mask', output_dir)
    if not out_path.exists():
        max_clip = float(config.get('max_porcentaje_clip', 10)) / 100.0
        speech, _ = _load_audio(sample['audio'])
        n = len(speech)
        mask_len = int(n * random.uniform(0.01, max(0.01, max_clip)))
        if mask_len == 0:
            return None
        mask_start = random.randint(0, max(0, n - mask_len))
        aumentado = speech.copy()
        aumentado[mask_start: mask_start + mask_len] = 0.0
        _save_audio(aumentado.astype(np.float32), out_path)
    return {'audio': str(out_path), 'sentence': sample['sentence']}


def _aug_eco(
    sample: Dict, config: Dict, output_dir: Path
) -> Optional[Dict]:
    import numpy as np
    out_path = _aug_path(sample, 'eco', output_dir)
    if not out_path.exists():
        delay_ms = int(config.get('delay_ms', 50))
        decay = float(config.get('decay', 0.2))
        speech, _ = _load_audio(sample['audio'])
        delay_samples = int(delay_ms * 16000 / 1000)
        eco = np.zeros_like(speech)
        if delay_samples < len(speech):
            tail_len = len(speech) - delay_samples
            eco[delay_samples:] = speech[:tail_len] * decay
        aumentado = np.clip(speech + eco, -1.0, 1.0).astype(np.float32)
        _save_audio(aumentado, out_path)
    return {'audio': str(out_path), 'sentence': sample['sentence']}


# ── Registro de técnicas ───────────────────────────────────────────────────

_TECNICAS = {
    'ruido_gaussiano': _aug_ruido_gaussiano,
    'cambio_velocidad': _aug_cambio_velocidad,
    'cambio_tono': _aug_cambio_tono,
    'reduccion_volumen': _aug_reduccion_volumen,
    'recorte_tiempo': _aug_recorte_tiempo,
    'eco': _aug_eco,
}
