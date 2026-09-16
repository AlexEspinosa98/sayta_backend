"""Permission classes de DRF derivadas dinámicamente del motor de roles."""

from rest_framework.permissions import BasePermission

from .services import registrar_auditoria, tiene_permiso


def requiere_permiso(modulo_codigo: str, accion_codigo: str, submodulo_codigo: str | None = None):
    """
    Factory de BasePermission para DRF.

    Uso: permission_classes = [requiere_permiso('glosario', 'editar')]
    Uso granular: permission_classes = [requiere_permiso('glosario', 'editar', 'terminos')]
    """

    class _RequierePermiso(BasePermission):
        message = f'No tienes permiso para "{accion_codigo}" en el módulo "{modulo_codigo}".'

        def has_permission(self, request, view):
            ok = tiene_permiso(request.user, modulo_codigo, accion_codigo, submodulo_codigo)
            if ok:
                registrar_auditoria(request, modulo_codigo, accion_codigo)
            return ok

    sufijo = f'_{submodulo_codigo}' if submodulo_codigo else ''
    _RequierePermiso.__name__ = f'RequierePermiso_{modulo_codigo}{sufijo}_{accion_codigo}'
    return _RequierePermiso
