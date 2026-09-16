"""
Chequeo de permisos para vistas planas de Django (no-DRF).

translator_api usa HttpRequest/JsonResponse en lugar de DRF, por lo que no pasa
por request.user vía sesión ni por las permission_classes de DRF. Este decorador
reutiliza TokenAuthentication de DRF para resolver el usuario desde el header
`Authorization: Token ...` y aplica el mismo motor de permisos que el resto del
sistema (roles.services.tiene_permiso).
"""

from functools import wraps

from django.http import JsonResponse
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .services import registrar_auditoria, tiene_permiso


def requiere_permiso_django(modulo_codigo: str, accion_codigo):
    """
    accion_codigo puede ser un string (misma acción para todos los métodos) o un
    dict {"GET": "ver", "PUT": "etiquetar", "DELETE": "eliminar"} para vistas que
    manejan varios métodos HTTP en una sola función.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            try:
                auth_result = TokenAuthentication().authenticate(request)
            except AuthenticationFailed as exc:
                return JsonResponse({'detail': str(exc)}, status=401)

            if not auth_result:
                return JsonResponse(
                    {'detail': 'Las credenciales de autenticación no se proveyeron.'},
                    status=401,
                )

            user, _token = auth_result
            request.user = user

            accion = (
                accion_codigo.get(request.method)
                if isinstance(accion_codigo, dict)
                else accion_codigo
            )
            if not accion or not tiene_permiso(user, modulo_codigo, accion):
                return JsonResponse(
                    {'detail': f'No tienes permiso para esta acción en el módulo "{modulo_codigo}".'},
                    status=403,
                )

            registrar_auditoria(request, modulo_codigo, accion)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
