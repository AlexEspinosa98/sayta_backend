from rest_framework.permissions import BasePermission


def _rol(user) -> str:
    try:
        return user.perfil.rol
    except Exception:
        return ''


class EsAdmin(BasePermission):
    """Solo administradores."""
    message = 'Se requiere rol de Administrador.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and _rol(request.user) == 'admin'


class EsInvestigador(BasePermission):
    """Investigadores, desarrolladores y administradores."""
    message = 'Se requiere rol de Investigador, Desarrollador o Administrador.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and _rol(request.user) in (
            'admin', 'desarrollador', 'investigador'
        )


class EsAnotador(BasePermission):
    """Anotadores, investigadores, desarrolladores y administradores."""
    message = 'Se requiere rol de Anotador o superior.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and _rol(request.user) in (
            'admin', 'desarrollador', 'investigador', 'anotador'
        )
