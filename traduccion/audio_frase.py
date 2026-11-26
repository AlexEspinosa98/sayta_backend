"""
Voz por piezas reales: una frase armada con el glosario se «lee» encadenando las grabaciones
reales de cada pieza (voz de hablantes de la comunidad, nunca síntesis).

Para que no suene a varias voces pegadas se prefieren clips de la misma jornada (y del mismo
hablante cuando hay metadatos). Cada clip se recorta de silencios, se iguala en volumen y se
encadena con una pausa corta. El resultado se cachea en memoria.
"""
import hashlib
import io
import logging
import threading
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from . import audio_ejemplo

logger = logging.getLogger(__name__)

SR = 16000
_PAUSA_S = 0.18
_TOP_DB = 32
_MAX_CACHE = 64
_cache: 'OrderedDict[str, Tuple[bytes, Dict]]' = OrderedDict()
_lock = threading.Lock()


def _clave(piezas: List[str], codigo: str) -> str:
    return hashlib.sha1(('|'.join(piezas) + '#' + codigo).encode('utf-8')).hexdigest()


def _hablante(e: Dict) -> str:
    try:
        from translator_api.models import AudioMetadato
        m = AudioMetadato.objects.filter(comunidad=e['comunidad'], jornada=e['jornada'], audio=e['audio']).only('hablante').first()
        return (m.hablante if m else '') or ''
    except Exception:
        return ''


def elegir_clips(piezas: List[str], codigo: str) -> Tuple[List[Optional[Dict]], Dict]:
    """
    Para cada pieza elige una grabación. Primero se busca la combinación (jornada, hablante) que
    cubra más piezas; dentro de ella se toma el primer clip. Devuelve la lista (None donde no hay
    audio) y un resumen.
    """
    opciones: List[List[Dict]] = [audio_ejemplo.ejemplos(p, codigo, 5) for p in piezas]
    for lista in opciones:
        for e in lista:
            e['_hablante'] = _hablante(e)
    # puntuar cada (jornada, hablante) por cuántas piezas cubre
    puntaje: Dict[Tuple[str, str], int] = {}
    for lista in opciones:
        vistos = set()
        for e in lista:
            k = (e['jornada'], e['_hablante'])
            if k in vistos:
                continue
            vistos.add(k)
            puntaje[k] = puntaje.get(k, 0) + 1
    orden = sorted(puntaje.items(), key=lambda kv: -kv[1])
    elegidos: List[Optional[Dict]] = []
    for lista in opciones:
        clip = None
        for (jornada, hablante), _ in orden:
            clip = next((e for e in lista if e['jornada'] == jornada and e['_hablante'] == hablante), None)
            if clip:
                break
        if clip is None and lista:
            clip = lista[0]
        elegidos.append(clip)
    resumen = {
        'piezas': len(piezas),
        'con_audio': sum(1 for c in elegidos if c),
        'faltantes': [p for p, c in zip(piezas, elegidos) if not c],
        'jornadas': sorted({c['jornada'] for c in elegidos if c}),
        'hablantes': sorted({c['_hablante'] for c in elegidos if c and c['_hablante']}),
    }
    return elegidos, resumen


def sintetizar(piezas: List[str], codigo: str) -> Tuple[Optional[bytes], Dict]:
    """
    Devuelve (wav_bytes | None, resumen). None si ninguna pieza tiene grabación.
    """
    piezas = [p.strip() for p in piezas if p and p.strip()]
    if not piezas:
        return None, {'piezas': 0, 'con_audio': 0, 'faltantes': [], 'jornadas': [], 'hablantes': []}
    k = _clave(piezas, codigo)
    with _lock:
        if k in _cache:
            _cache.move_to_end(k)
            return _cache[k]

    import librosa
    import numpy as np
    import soundfile as sf

    elegidos, resumen = elegir_clips(piezas, codigo)
    trozos = []
    pausa = np.zeros(int(SR * _PAUSA_S), dtype=np.float32)
    for clip in elegidos:
        if not clip:
            continue
        ruta = audio_ejemplo.ruta_archivo(clip['comunidad'], clip['jornada'], clip['audio'])
        if ruta is None:
            continue
        try:
            y, _ = librosa.load(str(ruta), sr=SR, mono=True)
        except Exception as exc:
            logger.warning('audio_frase: no se pudo leer %s: %s', ruta, exc)
            continue
        y, _ = librosa.effects.trim(y, top_db=_TOP_DB)
        if y.size == 0:
            continue
        rms = float(np.sqrt(np.mean(y ** 2))) or 1e-6
        y = (y * (0.08 / rms)).astype(np.float32)          # mismo nivel para todas las piezas
        # desvanecido corto en los bordes para que el corte no haga «clic»
        n_fade = min(int(SR * 0.012), y.size // 2)
        if n_fade > 0:
            rampa = np.linspace(0.0, 1.0, n_fade, dtype=np.float32)
            y[:n_fade] *= rampa
            y[-n_fade:] *= rampa[::-1]
        trozos.append(y)
        trozos.append(pausa)
    if not trozos:
        resumen['con_audio'] = 0
        return None, resumen
    senal = np.concatenate(trozos[:-1])
    pico = float(np.max(np.abs(senal))) or 1.0
    if pico > 0.95:
        senal = senal * (0.95 / pico)
    buf = io.BytesIO()
    sf.write(buf, senal, SR, format='WAV', subtype='PCM_16')
    datos = buf.getvalue()
    resumen['duracion_s'] = round(senal.size / SR, 2)
    with _lock:
        _cache[k] = (datos, resumen)
        while len(_cache) > _MAX_CACHE:
            _cache.popitem(last=False)
    return datos, resumen
