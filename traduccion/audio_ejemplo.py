"""
Audio de ejemplo real para una traducción: si en el corpus etiquetado hay una grabación cuya
transcripción coincide (normalizada) con el término, se ofrece como «así suena».
No es síntesis de voz: es la voz de un hablante de la comunidad ya grabada y etiquetada.

El índice (transcripción normalizada → grabaciones) se construye leyendo los .txt del corpus y
se refresca cada 10 minutos.
"""
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import lexico

logger = logging.getLogger(__name__)

COMUNIDAD_POR_LENGUA = {'1': 'Arhuaco', 'kogui': 'Kogui'}
_EXT_AUDIO = ('.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm')
_TTL = 600

_indice: Dict[str, Dict[str, List[Dict]]] = {}
_construido = 0.0
_lock = threading.Lock()


def _base() -> Path:
    from translator_api.views import _build_grabaciones_path
    return _build_grabaciones_path()


def _construir() -> Dict[str, Dict[str, List[Dict]]]:
    base = _base()
    idx: Dict[str, Dict[str, List[Dict]]] = {}
    if not base.exists():
        return idx
    for comunidad_dir in base.iterdir():
        if not comunidad_dir.is_dir():
            continue
        com = comunidad_dir.name
        por_texto: Dict[str, List[Dict]] = idx.setdefault(com, {})
        for jornada_dir in comunidad_dir.iterdir():
            proc = jornada_dir / 'audios_procesados'
            crudos = jornada_dir / 'audios_sin_procesar'
            if not proc.is_dir() or not crudos.is_dir():
                continue
            existentes = {p.stem: p.name for p in crudos.iterdir() if p.suffix.lower() in _EXT_AUDIO}
            for txt in proc.glob('*.txt'):
                nombre = existentes.get(txt.stem)
                if not nombre:
                    continue
                try:
                    etiqueta = txt.read_text(encoding='utf-8', errors='ignore').strip()
                except OSError:
                    continue
                k = lexico.normalizar(etiqueta)
                if not k or len(k) > 300:
                    continue
                lista = por_texto.setdefault(k, [])
                if len(lista) < 5:
                    lista.append({'comunidad': com, 'jornada': jornada_dir.name, 'audio': nombre, 'etiqueta': etiqueta})
    return idx


def indice() -> Dict[str, Dict[str, List[Dict]]]:
    global _indice, _construido
    if _indice and time.time() - _construido < _TTL:
        return _indice
    with _lock:
        if _indice and time.time() - _construido < _TTL:
            return _indice
        t0 = time.time()
        try:
            _indice = _construir()
            _construido = time.time()
            logger.info('Índice de audios de ejemplo: %s (%.1f s)', {c: len(v) for c, v in _indice.items()}, time.time() - t0)
        except Exception as exc:
            logger.warning('No se pudo construir el índice de audios de ejemplo: %s', exc)
            _construido = time.time()
    return _indice


def comunidad(codigo_lengua: str) -> Optional[str]:
    return COMUNIDAD_POR_LENGUA.get((codigo_lengua or '').lower())


def ejemplos(texto: str, codigo_lengua: str, maximo: int = 3) -> List[Dict]:
    com = comunidad(codigo_lengua)
    if not com:
        return []
    return list(indice().get(com, {}).get(lexico.normalizar(texto), []))[:maximo]


def tiene_ejemplo(texto: str, codigo_lengua: str) -> bool:
    return bool(ejemplos(texto, codigo_lengua, 1))


def ruta_archivo(comunidad_nombre: str, jornada: str, audio: str) -> Optional[Path]:
    """Ruta segura del audio (sin salir de la carpeta de grabaciones)."""
    base = _base().resolve()
    p = (base / comunidad_nombre / jornada / 'audios_sin_procesar' / audio).resolve()
    if base not in p.parents or not p.is_file():
        return None
    return p
