"""
Progreso en vivo de un entrenamiento y métricas de reconocimiento de voz (ASR).

* El hilo de entrenamiento escribe un archivo `progreso.json` dentro de la carpeta del experimento
  (así lo ven los 2 workers de gunicorn y sobrevive a lecturas concurrentes).
* Los endpoints `/experimentos/<id>/progreso/` y `/procesos/` solo leen ese archivo.
* PER (tasa de error de fonemas): como las lenguas indígenas no tienen un conversor texto→fonemas estándar,
  se calcula de forma APROXIMADA sobre las unidades de la escritura (dígrafos como `ch`, `ll`, `ts`… cuentan
  como una sola unidad y las marcas diacríticas se pegan a su letra). Se documenta así en la Guía.
"""

import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Si no llega ningún latido en tanto tiempo, el proceso se considera colgado.
UMBRAL_COLGADO_SEGUNDOS = 600
HISTORIAL_MAX_PUNTOS = 400

# Dígrafos/trígrafos habituales en las ortografías prácticas de las lenguas de la Sierra Nevada (y el español).
DIGRAFOS = ('ngw', 'kw', 'gw', 'ch', 'll', 'rr', 'ts', 'dz', 'ng', 'ny', 'sh', 'zh', 'th', 'kh', 'tx')


def carpeta_experimento(exp_id: str) -> Path:
    from django.conf import settings
    base = getattr(settings, 'MODELOS_ENTRENADOS_DIR', str(Path(settings.BASE_DIR) / 'modelos_entrenados'))
    return Path(base) / str(exp_id)


def ruta_progreso(exp_id: str) -> Path:
    return carpeta_experimento(exp_id) / 'progreso.json'


def leer_progreso(exp_id: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(ruta_progreso(exp_id).read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError, OSError):
        return None


def _escribir(exp_id: str, datos: Dict[str, Any]) -> None:
    ruta = ruta_progreso(exp_id)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_suffix('.tmp')
        tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding='utf-8')
        os.replace(tmp, ruta)
    except OSError as exc:  # el progreso nunca debe tumbar el entrenamiento
        logger.debug('No se pudo escribir progreso: %s', exc)


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return f if f == f and abs(f) != float('inf') else None
    except (TypeError, ValueError):
        return None


def crear_callback(exp_id: str, fold: Optional[int] = None, folds_total: int = 1):
    """TrainerCallback que deja el progreso en disco (latido, época, paso, pérdida, historial)."""
    from transformers import TrainerCallback

    class _Progreso(TrainerCallback):
        def __init__(self):
            self.datos: Dict[str, Any] = leer_progreso(exp_id) or {
                'fase': 'preparando', 'historial_loss': [], 'historial_eval': [],
                'inicio_ts': time.time(),
            }
            self.datos.setdefault('historial_loss', [])
            self.datos.setdefault('historial_eval', [])
            self.datos.setdefault('inicio_ts', time.time())
            self._ultimo_guardado = 0.0
            self.datos['fold'] = fold
            self.datos['folds_total'] = folds_total

        def _guardar(self, force: bool = False):
            ahora = time.time()
            if not force and ahora - self._ultimo_guardado < 5:
                return
            self._ultimo_guardado = ahora
            self.datos['heartbeat_ts'] = ahora
            self.datos['heartbeat'] = datetime.now(timezone.utc).isoformat()
            _escribir(exp_id, self.datos)

        def _estado(self, state):
            self.datos['step_actual'] = int(state.global_step or 0)
            self.datos['steps_totales'] = int(state.max_steps) if state.max_steps else None
            self.datos['epoca_actual'] = float(state.epoch or 0.0)

        def on_train_begin(self, args, state, control, **kw):
            self.datos['fase'] = 'entrenando'
            self.datos['epocas_totales'] = float(args.num_train_epochs)
            self.datos['inicio_fase_ts'] = time.time()
            self._estado(state)
            self._guardar(force=True)

        def on_step_end(self, args, state, control, **kw):
            self.datos['fase'] = 'entrenando'
            self._estado(state)
            self._guardar()

        def on_log(self, args, state, control, logs=None, **kw):
            if not logs:
                return
            self._estado(state)
            loss = _num(logs.get('loss'))
            if loss is not None:
                self.datos['loss_actual'] = loss
                h = self.datos['historial_loss']
                h.append([int(state.global_step), round(loss, 4)])
                if len(h) > HISTORIAL_MAX_PUNTOS:        # adelgaza el historial conservando la forma
                    self.datos['historial_loss'] = h[::2]
            for k_src, k_dst in (('learning_rate', 'learning_rate'), ('grad_norm', 'grad_norm')):
                v = _num(logs.get(k_src))
                if v is not None:
                    self.datos[k_dst] = v
            self._guardar(force=True)

        def on_prediction_step(self, args, state, control, **kw):
            self.datos['fase'] = 'evaluando'
            self._guardar()

        def on_evaluate(self, args, state, control, metrics=None, **kw):
            metrics = metrics or {}
            punto = {'epoca': round(float(state.epoch or 0.0), 2), 'step': int(state.global_step or 0)}
            for k in ('eval_loss', 'eval_wer', 'eval_cer', 'eval_per'):
                v = _num(metrics.get(k))
                if v is not None:
                    punto[k] = round(v, 4)
            self.datos['historial_eval'].append(punto)
            self.datos['fase'] = 'entrenando'
            self._estado(state)
            self._guardar(force=True)

        def on_train_end(self, args, state, control, **kw):
            self.datos['fase'] = 'finalizando'
            self._estado(state)
            self._guardar(force=True)

    return _Progreso()


def marcar_fase(exp_id: str, fase: str) -> None:
    datos = leer_progreso(exp_id) or {'historial_loss': [], 'historial_eval': [], 'inicio_ts': time.time()}
    datos['fase'] = fase
    datos['heartbeat_ts'] = time.time()
    datos['heartbeat'] = datetime.now(timezone.utc).isoformat()
    _escribir(exp_id, datos)


def resumen(exp, detalle: bool = False) -> Dict[str, Any]:
    """Forma que consumen el monitor (/progreso/) y la lista de procesos (/procesos/)."""
    d = leer_progreso(str(exp.id)) or {}
    hb = d.get('heartbeat_ts')
    seg = int(time.time() - hb) if hb else None
    epocas = d.get('epocas_totales') or (exp.config_entrenamiento or {}).get('num_train_epochs')
    epocas = float(epocas) if epocas else None
    epoca = float(d.get('epoca_actual') or 0.0)
    steps_tot = d.get('steps_totales')
    step = int(d.get('step_actual') or 0)
    if steps_tot:
        pct = 100.0 * step / steps_tot
    elif epocas:
        pct = 100.0 * epoca / epocas
    else:
        pct = 0.0
    pct = max(0.0, min(100.0, pct))

    # Tiempo restante estimado a partir del ritmo medio desde que empezó el entrenamiento real
    eta = None
    t0 = d.get('inicio_fase_ts')
    if t0 and steps_tot and step > 0:
        transcurrido = time.time() - t0
        eta = int(transcurrido * (steps_tot - step) / step)
    transcurrido_total = int(time.time() - d['inicio_ts']) if d.get('inicio_ts') else None

    colgado = bool(seg is not None and seg > UMBRAL_COLGADO_SEGUNDOS and exp.estado == 'entrenando')
    out = {
        'experimento_id': str(exp.id), 'nombre': exp.nombre, 'estado': exp.estado,
        'lengua': exp.lengua.codigo, 'modelo': exp.modelo_base.nombre_hf,
        'fase': d.get('fase', 'preparando'),
        'epoca_actual': epoca, 'epocas_totales': epocas,
        'step_actual': step, 'steps_totales': steps_tot,
        'porcentaje': round(pct, 1), 'loss_actual': d.get('loss_actual'),
        'learning_rate': d.get('learning_rate'), 'grad_norm': d.get('grad_norm'),
        'ultimo_heartbeat': d.get('heartbeat'), 'segundos_desde_heartbeat': seg,
        'esta_vivo': (seg is not None and seg <= UMBRAL_COLGADO_SEGUNDOS) if seg is not None else None,
        'colgado': colgado, 'created_at': exp.created_at,
        'segundos_transcurridos': transcurrido_total, 'segundos_restantes': eta,
        'fold': d.get('fold'), 'folds_total': d.get('folds_total'),
    }
    if detalle:
        out['historial_loss'] = d.get('historial_loss', [])
        out['historial_eval'] = d.get('historial_eval', [])
    return out


# ------------------------------------------------------------------
# PER aproximado
# ------------------------------------------------------------------

_SOLO_LETRAS = re.compile(r"[^\w]|[\d_]", re.UNICODE)


def unidades_fonemicas(texto: str) -> List[str]:
    """Divide un texto en unidades parecidas a fonemas (ver cabecera del módulo)."""
    t = unicodedata.normalize('NFD', (texto or '').lower())
    # Marcas combinantes (tilde, diéresis, tilde nasal…) se pegan a su letra base
    unidades: List[str] = []
    for ch in t:
        if unicodedata.combining(ch):
            if unidades:
                unidades[-1] += ch
            continue
        if _SOLO_LETRAS.match(ch) or ch.isspace():
            continue
        unidades.append(ch)
    # Unir dígrafos/trígrafos
    out: List[str] = []
    i = 0
    while i < len(unidades):
        for dg in DIGRAFOS:
            n = len(dg)
            if ''.join(u[:1] for u in unidades[i:i + n]) == dg and all(len(u) == 1 for u in unidades[i:i + n]):
                out.append(dg)
                i += n
                break
        else:
            out.append(unidades[i])
            i += 1
    return out


def per_aproximado(predicciones: List[str], referencias: List[str]) -> float:
    """Tasa de error de fonemas (aprox.) = (sustituciones + borrados + inserciones) / unidades de referencia."""
    import jiwer
    tabla: Dict[str, str] = {}

    def codifica(texto: str) -> str:
        # cada unidad pasa a una "palabra" distinta para que jiwer.wer cuente errores por unidad
        return ' '.join(tabla.setdefault(u, f'u{len(tabla)}') for u in unidades_fonemicas(texto))

    refs, hips = [], []
    for ref, hip in zip(referencias, predicciones):
        r = codifica(ref)
        if not r:           # referencia sin unidades: no aporta
            continue
        refs.append(r)
        hips.append(codifica(hip))
    if not refs:
        return 1.0
    return float(jiwer.wer(refs, hips))
