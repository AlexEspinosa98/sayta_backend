"""
Gestión del espacio que ocupan los modelos entrenados.

Cada experimento guarda sus archivos en  MODELOS_ENTRENADOS_DIR/<id del experimento>/ :
  * el modelo final (adapter_model.safetensors / model.safetensors …) en la raíz de la carpeta,
  * decenas de `checkpoint-N/` intermedios (lo que más pesa),
  * a veces `augmented/` (audios aumentados temporales).

Borrar archivos NUNCA toca el registro del experimento en la base de datos ni sus métricas en MLflow:
las estadísticas para analizar qué salió mal se conservan.
"""
import logging
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from entrenamiento.models import ExperimentoEntrenamiento as Exp

logger = logging.getLogger(__name__)

ARCHIVOS_MODELO_FINAL = ('adapter_model.safetensors', 'model.safetensors', 'pytorch_model.bin', 'adapter_model.bin')
CARPETAS_TEMPORALES = ('augmented',)
ESTADOS_EN_USO = (Exp.ESTADO_PENDIENTE, Exp.ESTADO_ENTRENANDO)


class AlmacenamientoError(Exception):
    pass


def raiz() -> Path:
    return Path(getattr(settings, 'MODELOS_ENTRENADOS_DIR', str(Path(settings.BASE_DIR) / 'modelos_entrenados')))


def carpeta_segura(nombre: str) -> Path:
    """Resuelve <raiz>/<nombre> garantizando que queda directamente dentro de la raíz."""
    base = raiz().resolve()
    ruta = (base / nombre).resolve()
    if ruta.parent != base or ruta == base:
        raise AlmacenamientoError('Ruta fuera del directorio de modelos.')
    return ruta


def tamano(ruta: Path) -> int:
    total = 0
    if ruta.is_symlink():
        return 0
    if ruta.is_file():
        return ruta.stat().st_size
    for actual, _dirs, archivos in os.walk(ruta):
        for a in archivos:
            try:
                total += os.lstat(os.path.join(actual, a)).st_size
            except OSError:
                pass
    return total


def _subcarpetas_a_limpiar(carpeta: Path):
    if not carpeta.exists():
        return []
    return [d for d in carpeta.iterdir()
            if d.is_dir() and not d.is_symlink() and (d.name.startswith('checkpoint-') or d.name in CARPETAS_TEMPORALES)]


def inspeccionar(carpeta: Path) -> dict:
    """Resumen de lo que hay en la carpeta de un experimento."""
    if not carpeta.exists():
        return {'existe': False, 'bytes': 0, 'checkpoints': 0, 'bytes_liberables': 0, 'tiene_modelo_final': False}
    limpiables = _subcarpetas_a_limpiar(carpeta)
    return {
        'existe': True,
        'bytes': tamano(carpeta),
        'checkpoints': sum(1 for d in limpiables if d.name.startswith('checkpoint-')),
        'bytes_liberables': sum(tamano(d) for d in limpiables),
        'tiene_modelo_final': any((carpeta / f).exists() for f in ARCHIVOS_MODELO_FINAL),
    }


def limpiar_checkpoints(exp: Exp) -> int:
    """Borra checkpoints intermedios y audios aumentados; conserva el modelo final. Devuelve bytes liberados."""
    if exp.estado in ESTADOS_EN_USO:
        raise AlmacenamientoError('El experimento está entrenando: no se puede limpiar.')
    carpeta = carpeta_segura(str(exp.id))
    liberado = 0
    for d in _subcarpetas_a_limpiar(carpeta):
        liberado += tamano(d)
        shutil.rmtree(d, ignore_errors=True)
    if liberado:
        exp.bytes_liberados = (exp.bytes_liberados or 0) + liberado
        exp.save(update_fields=['bytes_liberados'])
    logger.info('Checkpoints borrados: experimento=%s liberado=%s', exp.id, liberado)
    return liberado


def eliminar_modelo(exp: Exp) -> int:
    """Borra TODA la carpeta del experimento (modelo final incluido). Conserva registro y métricas."""
    if exp.estado in ESTADOS_EN_USO:
        raise AlmacenamientoError('El experimento está entrenando: no se puede eliminar.')
    if exp.estado == Exp.ESTADO_ACTIVO or exp.is_active:
        raise AlmacenamientoError('Es el modelo ACTIVO de su lengua: activa otro modelo antes de eliminarlo.')
    carpeta = carpeta_segura(str(exp.id))
    # Un reentrenamiento hecho sobre pesos completos de este modelo necesita esta carpeta para funcionar.
    dependientes = [h.nombre for h in Exp.objects.filter(reentrenado_de=exp, modelo_eliminado_en__isnull=True)
                    if (h.config_entrenamiento or {}).get('depende_de_ruta') == (exp.ruta_modelo_entrenado or str(carpeta))
                    and h.estado in (Exp.ESTADO_COMPLETADO, Exp.ESTADO_ACTIVO)]
    if dependientes:
        raise AlmacenamientoError(
            'Hay modelos reentrenados a partir de este que lo necesitan: ' + ', '.join(dependientes) +
            '. Bórralos primero o conserva este modelo.')
    liberado = tamano(carpeta) if carpeta.exists() else 0
    if carpeta.exists():
        shutil.rmtree(carpeta, ignore_errors=True)
    exp.ruta_modelo_entrenado = ''
    exp.modelo_eliminado_en = timezone.now()
    exp.bytes_liberados = (exp.bytes_liberados or 0) + liberado
    exp.save(update_fields=['ruta_modelo_entrenado', 'modelo_eliminado_en', 'bytes_liberados'])
    logger.info('Modelo eliminado: experimento=%s liberado=%s', exp.id, liberado)
    return liberado


def resumen_almacenamiento() -> dict:
    base = raiz()
    experimentos = []
    ids = set()
    for exp in Exp.objects.select_related('lengua', 'modelo_base').order_by('-created_at'):
        ids.add(str(exp.id))
        info = inspeccionar(base / str(exp.id)) if base.exists() else {'existe': False, 'bytes': 0, 'checkpoints': 0, 'bytes_liberables': 0, 'tiene_modelo_final': False}
        experimentos.append({
            'id': str(exp.id), 'nombre': exp.nombre, 'lengua': exp.lengua.nombre,
            'estado': exp.estado, 'is_active': exp.is_active,
            'created_at': exp.created_at.isoformat(),
            'modelo_eliminado_en': exp.modelo_eliminado_en.isoformat() if exp.modelo_eliminado_en else None,
            'bytes_liberados': exp.bytes_liberados or 0,
            'mlflow_run_id': exp.mlflow_run_id,
            'metricas': exp.metricas or {},
            **info,
        })
    huerfanas = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if d.is_dir() and d.name not in ids:
                huerfanas.append({'carpeta': d.name, 'bytes': tamano(d)})
    total = sum(e['bytes'] for e in experimentos) + sum(h['bytes'] for h in huerfanas)
    try:
        du = shutil.disk_usage(base if base.exists() else '/')
        disco = {'total': du.total, 'libre': du.free}
    except OSError:
        disco = {'total': 0, 'libre': 0}
    return {
        'raiz': str(base), 'total_bytes': total,
        'liberable_bytes': sum(e['bytes_liberables'] for e in experimentos),
        'disco': disco, 'experimentos': experimentos, 'huerfanas': huerfanas,
    }


def limpiar_masivo(modo: str) -> dict:
    """
    modo = 'checkpoints'  -> borra checkpoints/temporales de TODOS los experimentos (conserva modelos finales).
    modo = 'fallidos'     -> borra la carpeta completa de los experimentos FALLIDOS (no tienen modelo utilizable).
    modo = 'huerfanas'    -> borra carpetas sin experimento en la base de datos.
    """
    liberado, tocados, omitidos = 0, 0, []
    if modo == 'huerfanas':
        ids = {str(i) for i in Exp.objects.values_list('id', flat=True)}
        base = raiz()
        for d in (sorted(base.iterdir()) if base.exists() else []):
            if d.is_dir() and not d.is_symlink() and d.name not in ids:
                b = tamano(d); shutil.rmtree(d, ignore_errors=True); liberado += b; tocados += 1
        return {'modo': modo, 'tocados': tocados, 'liberado_bytes': liberado, 'omitidos': omitidos}
    qs = Exp.objects.all()
    if modo == 'fallidos':
        qs = qs.filter(estado=Exp.ESTADO_FALLIDO)
    elif modo != 'checkpoints':
        raise AlmacenamientoError('Modo no válido.')
    for exp in qs:
        try:
            b = limpiar_checkpoints(exp) if modo == 'checkpoints' else eliminar_modelo(exp)
        except AlmacenamientoError as e:
            omitidos.append({'id': str(exp.id), 'nombre': exp.nombre, 'motivo': str(e)})
            continue
        if b:
            tocados += 1
            liberado += b
    return {'modo': modo, 'tocados': tocados, 'liberado_bytes': liberado, 'omitidos': omitidos}
