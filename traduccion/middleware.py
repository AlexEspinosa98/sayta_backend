"""Guarda el usuario de la petición en un thread-local para que las señales del historial sepan quién cambió qué."""
import threading

_local = threading.local()


def usuario_actual():
    return getattr(_local, 'usuario', None)


def origen_actual():
    return getattr(_local, 'origen', '')


class UsuarioActualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.usuario = None
        _local.origen = 'api'
        try:
            # DRF autentica después del middleware; se resuelve perezosamente en la señal.
            _local.request = request
            return self.get_response(request)
        finally:
            _local.usuario = None
            _local.request = None
            _local.origen = ''


def _resolver_usuario():
    req = getattr(_local, 'request', None)
    if req is None:
        return None
    u = getattr(req, 'user', None)
    if u is not None and getattr(u, 'is_authenticated', False):
        return u
    # DRF: token en cabecera, aún no evaluado por el middleware de sesión
    try:
        from rest_framework.authentication import TokenAuthentication
        res = TokenAuthentication().authenticate(req)
        if res:
            return res[0]
    except Exception:
        pass
    return None
