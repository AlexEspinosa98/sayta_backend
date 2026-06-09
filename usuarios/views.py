"""
Autenticación y gestión de usuarios.

Endpoints:
  POST /api/auth/login/               Obtener token de acceso
  POST /api/auth/logout/              Invalidar token actual
  GET  /api/auth/perfil/              Perfil del usuario autenticado
  POST /api/auth/registro/            Registrar nuevo usuario (solo admin)
  GET  /api/auth/usuarios/            Listar todos los usuarios (solo admin)
  GET  /api/auth/usuarios/<id>/       Detalle de un usuario (solo admin)
  PATCH /api/auth/usuarios/<id>/      Actualizar usuario o rol (solo admin)
  DELETE /api/auth/usuarios/<id>/     Desactivar usuario (solo admin)
"""

import logging

from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PerfilUsuario
from .permissions import EsAdmin
from .serializers import (
    ActualizarUsuarioSerializer,
    LoginSerializer,
    RegistroSerializer,
    UsuarioSerializer,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Setup inicial — registrar el primer admin sin token
# ──────────────────────────────────────────────────────────────────────────────

class SetupAdminView(APIView):
    """
    Endpoint público para crear el primer usuario admin.
    Solo funciona cuando NO existe ningún usuario con rol 'admin' en el sistema.
    Una vez que hay al menos un admin, este endpoint devuelve 403.
    """
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=['Auth'],
        summary='Crear primer administrador (solo si no hay ninguno)',
        description=(
            'Endpoint de configuración inicial. Crea el primer usuario con rol `admin`.\n\n'
            '**Solo funciona cuando no existe ningún administrador en el sistema.**\n'
            'Una vez creado el primer admin, este endpoint devuelve `403` permanentemente.\n\n'
            'Usar solo en el despliegue inicial. Para crear más usuarios después, '
            'usar `POST /api/auth/registro/` con el token del admin.'
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'admin'},
                    'email': {'type': 'string', 'example': 'admin@sayta.co'},
                    'password': {'type': 'string', 'example': 'MiClave2026!'},
                    'first_name': {'type': 'string', 'example': 'Admin'},
                    'last_name': {'type': 'string', 'example': 'Sayta'},
                },
                'required': ['username', 'email', 'password'],
            }
        },
        responses={
            201: OpenApiResponse(description='Admin creado, token incluido en la respuesta'),
            400: OpenApiResponse(description='Datos inválidos'),
            403: OpenApiResponse(description='Ya existe al menos un administrador en el sistema'),
        },
        auth=[],
    )
    def post(self, request):
        ya_hay_admin = (
            PerfilUsuario.objects.filter(rol=PerfilUsuario.ROL_ADMIN).exists()
        )
        if ya_hay_admin:
            return Response(
                {
                    'error': (
                        'Ya existe un administrador en el sistema. '
                        'Usa POST /api/auth/login/ para obtener un token '
                        'y POST /api/auth/registro/ para crear más usuarios.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data['rol'] = PerfilUsuario.ROL_ADMIN

        serializer = RegistroSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        # Hacer también superuser para poder entrar al admin de Django
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])

        token, _ = Token.objects.get_or_create(user=user)
        logger.info('Primer admin creado via setup: %s', user.username)

        return Response(
            {
                'mensaje': f'Administrador "{user.username}" creado correctamente.',
                'token': token.key,
                'usuario': UsuarioSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Login / Logout
# ──────────────────────────────────────────────────────────────────────────────

class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=['Auth'],
        summary='Iniciar sesión y obtener token',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'admin'},
                    'password': {'type': 'string', 'example': 'contraseña123'},
                },
                'required': ['username', 'password'],
            }
        },
        responses={
            200: OpenApiResponse(description='Token de acceso y datos del usuario'),
            400: OpenApiResponse(description='Credenciales incorrectas'),
        },
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'token': 'abc123def456...',
                    'usuario': {
                        'id': 1,
                        'username': 'admin',
                        'email': 'admin@sayta.co',
                        'nombre': 'Admin Sayta',
                        'rol': 'admin',
                        'rol_display': 'Administrador',
                    },
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
        auth=[],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)

        nombre = f'{user.first_name} {user.last_name}'.strip() or user.username
        try:
            rol = user.perfil.rol
            rol_display = user.perfil.get_rol_display()
        except PerfilUsuario.DoesNotExist:
            rol = None
            rol_display = None

        logger.info('Login exitoso: %s [%s]', user.username, rol)
        return Response({
            'token': token.key,
            'usuario': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nombre': nombre,
                'rol': rol,
                'rol_display': rol_display,
            },
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auth'],
        summary='Cerrar sesión e invalidar token',
        responses={200: OpenApiResponse(description='Sesión cerrada')},
    )
    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Token.DoesNotExist:
            pass
        logger.info('Logout: %s', request.user.username)
        return Response({'mensaje': 'Sesión cerrada correctamente.'})


# ──────────────────────────────────────────────────────────────────────────────
# Perfil propio
# ──────────────────────────────────────────────────────────────────────────────

class PerfilView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auth'],
        summary='Perfil del usuario autenticado',
        responses={200: UsuarioSerializer},
    )
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)


# ──────────────────────────────────────────────────────────────────────────────
# Registro (admin)
# ──────────────────────────────────────────────────────────────────────────────

class RegistroView(APIView):
    permission_classes = [EsAdmin]

    @extend_schema(
        tags=['Auth — Administración'],
        summary='Registrar nuevo usuario (solo admin)',
        description=(
            'Crea un usuario con su rol asignado.\n\n'
            '**Roles disponibles:**\n'
            '- `admin` → acceso total, puede gestionar usuarios\n'
            '- `investigador` → gestiona lenguas, términos, embeddings y entrenamiento\n'
            '- `anotador` → puede subir y etiquetar audios\n'
            '- `consultor` → acceso de solo lectura y transcripción\n'
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'maria.lopez'},
                    'email': {'type': 'string', 'example': 'maria@unimagdalena.edu.co'},
                    'password': {'type': 'string', 'example': 'contraseña123'},
                    'first_name': {'type': 'string', 'example': 'María'},
                    'last_name': {'type': 'string', 'example': 'López'},
                    'rol': {
                        'type': 'string',
                        'enum': ['admin', 'investigador', 'anotador', 'consultor'],
                        'example': 'anotador',
                    },
                },
                'required': ['username', 'email', 'password', 'rol'],
            }
        },
        responses={
            201: OpenApiResponse(description='Usuario creado exitosamente'),
            400: OpenApiResponse(description='Datos inválidos o usuario ya existe'),
            403: OpenApiResponse(description='Se requiere rol de Administrador'),
        },
    )
    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        logger.info('Usuario registrado: %s por %s', user.username, request.user.username)
        return Response(
            {
                'mensaje': f'Usuario "{user.username}" registrado correctamente.',
                'usuario': UsuarioSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Gestión de usuarios (admin)
# ──────────────────────────────────────────────────────────────────────────────

class UsuariosListView(APIView):
    permission_classes = [EsAdmin]

    @extend_schema(
        tags=['Auth — Administración'],
        summary='Listar todos los usuarios registrados',
        responses={200: UsuarioSerializer(many=True)},
    )
    def get(self, request):
        users = User.objects.select_related('perfil').all().order_by('username')
        return Response({
            'total': users.count(),
            'usuarios': UsuarioSerializer(users, many=True).data,
        })


class UsuarioDetailView(APIView):
    permission_classes = [EsAdmin]

    def _get_user(self, pk):
        try:
            return User.objects.select_related('perfil').get(pk=pk)
        except User.DoesNotExist:
            return None

    @extend_schema(
        tags=['Auth — Administración'],
        summary='Detalle de un usuario',
        responses={
            200: UsuarioSerializer,
            404: OpenApiResponse(description='Usuario no encontrado'),
        },
    )
    def get(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UsuarioSerializer(user).data)

    @extend_schema(
        tags=['Auth — Administración'],
        summary='Actualizar datos o rol de un usuario',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string'},
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'rol': {'type': 'string', 'enum': ['admin', 'investigador', 'anotador', 'consultor']},
                    'is_active': {'type': 'boolean'},
                    'password': {'type': 'string', 'minLength': 8},
                },
            }
        },
        responses={
            200: UsuarioSerializer,
            400: OpenApiResponse(description='Datos inválidos'),
            404: OpenApiResponse(description='Usuario no encontrado'),
        },
    )
    def patch(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ActualizarUsuarioSerializer(
            data=request.data, context={'user_id': pk}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        rol = data.pop('rol', None)
        password = data.pop('password', None)

        for field, value in data.items():
            setattr(user, field, value)

        if password:
            user.set_password(password)

        user.save()

        if rol:
            perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
            perfil.rol = rol
            perfil.save(update_fields=['rol', 'updated_at'])

        logger.info('Usuario actualizado: %s por %s', user.username, request.user.username)
        return Response(UsuarioSerializer(user).data)

    @extend_schema(
        tags=['Auth — Administración'],
        summary='Desactivar un usuario (no lo elimina)',
        responses={
            200: OpenApiResponse(description='Usuario desactivado'),
            404: OpenApiResponse(description='Usuario no encontrado'),
        },
    )
    def delete(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if user.pk == request.user.pk:
            return Response(
                {'error': 'No puedes desactivar tu propia cuenta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = False
        user.save(update_fields=['is_active'])
        # Invalidar token si existe
        Token.objects.filter(user=user).delete()

        logger.info('Usuario desactivado: %s por %s', user.username, request.user.username)
        return Response({'mensaje': f'Usuario "{user.username}" desactivado.'})
