"""Señales que registran el historial de cambios de TerminoLeng."""
import logging

from django.db.models.signals import post_delete, post_save, pre_save

from .middleware import _resolver_usuario, origen_actual

logger = logging.getLogger(__name__)
_CAMPOS = ('termino', 'termino_es_id', 'definicion', 'pos', 'sinonimos', 'ejemplos', 'tipo_morfema', 'activo')


def _snap(obj):
    d = {c: getattr(obj, c) for c in _CAMPOS}
    try:
        d['termino_es'] = obj.termino_es.termino if obj.termino_es_id else ''
    except Exception:
        d['termino_es'] = ''
    d.pop('termino_es_id', None)
    return d


def _registrar(instancia, accion, cambios):
    from .models import HistorialTermino
    try:
        u = _resolver_usuario()
        HistorialTermino.objects.create(
            termino=instancia if accion != 'eliminar' else None, termino_id_original=instancia.pk, termino_texto=(instancia.termino or '')[:255],
            lengua_codigo=instancia.lengua.codigo if instancia.lengua_id else '', accion=accion, cambios=cambios,
            usuario=u, usuario_nombre=((u.get_full_name() or u.username) if u else '')[:150], origen=origen_actual() or 'sistema',
        )
    except Exception as exc:
        logger.warning('No se pudo registrar historial del término %s: %s', instancia.pk, exc)


def _pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._antes = _snap(sender.objects.select_related('termino_es').get(pk=instance.pk))
        except sender.DoesNotExist:
            instance._antes = None
    else:
        instance._antes = None


def _post_save(sender, instance, created, **kwargs):
    if created:
        _registrar(instance, 'crear', {k: {'antes': None, 'despues': v} for k, v in _snap(instance).items() if v not in (None, '', [], False)})
        return
    antes = getattr(instance, '_antes', None)
    if antes is None:
        return
    despues = _snap(instance)
    cambios = {k: {'antes': antes[k], 'despues': despues[k]} for k in despues if antes.get(k) != despues[k]}
    if not cambios:
        return
    if list(cambios) == ['activo']:
        accion = 'restaurar' if despues['activo'] else 'desactivar'
    else:
        accion = 'editar'
    _registrar(instance, accion, cambios)


def _post_delete(sender, instance, **kwargs):
    _registrar(instance, 'eliminar', {'termino': {'antes': instance.termino, 'despues': None}})


def conectar():
    from terminos.models import TerminoLeng
    pre_save.connect(_pre_save, sender=TerminoLeng, weak=False, dispatch_uid='historial-termino-pre')
    post_save.connect(_post_save, sender=TerminoLeng, weak=False, dispatch_uid='historial-termino-post')
    post_delete.connect(_post_delete, sender=TerminoLeng, weak=False, dispatch_uid='historial-termino-del')
