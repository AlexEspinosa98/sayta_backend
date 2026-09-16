"""Motor de autorización: única fuente de verdad para chequeo de permisos y auditoría."""

import logging

from .models import Auditoria, RolPermiso

logger = logging.getLogger(__name__)

# Las acciones de solo lectura no generan rastro — evita ruido en la auditoría.
ACCIONES_NO_AUDITADAS = {'ver'}


def tiene_permiso(user, modulo_codigo: str, accion_codigo: str) -> bool:
    """
    True si `user` puede ejecutar `accion_codigo` dentro de `modulo_codigo`.

    is_superuser siempre pasa — válvula de seguridad para nunca bloquear
    al superusuario por un error de configuración en la matriz de roles.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    try:
        rol = user.perfil.rol
    except Exception:
        return False
    if rol is None or not rol.activo:
        return False
    return RolPermiso.objects.filter(
        rol=rol,
        permiso__modulo__codigo=modulo_codigo,
        permiso__codigo=accion_codigo,
    ).exists()


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def registrar_auditoria(request, modulo_codigo: str, accion_codigo: str, objeto_id: str = ''):
    """Deja rastro de una acción concedida. Nunca bloquea la request si falla."""
    if accion_codigo in ACCIONES_NO_AUDITADAS:
        return
    user = getattr(request, 'user', None)
    try:
        Auditoria.objects.create(
            usuario=user if user and getattr(user, 'is_authenticated', False) else None,
            modulo=modulo_codigo,
            accion=accion_codigo,
            metodo_http=request.method,
            ruta=request.path,
            objeto_id=str(objeto_id or ''),
            ip=_client_ip(request),
        )
    except Exception:
        logger.exception('No se pudo registrar auditoría (%s.%s)', modulo_codigo, accion_codigo)
