"""
Autenticación y gestión de usuarios.

Endpoints:
  POST /api/auth/login/               Obtener token de acceso
  POST /api/auth/logout/              Invalidar token actual
  GET  /api/auth/perfil/              Perfil del usuario autenticado
  PATCH /api/auth/perfil/             Actualizar perfil propio
  GET  /api/auth/permisos/            Permisos efectivos del usuario autenticado
  POST /api/auth/registro/            Registrar nuevo usuario (solo admin)
  POST /api/auth/registro-publico/    Auto-registro público (nace con rol "pendiente", sin permisos)
  GET  /api/auth/usuarios/            Listar todos los usuarios (solo admin)
  GET  /api/auth/usuarios/<id>/       Detalle de un usuario (solo admin)
  PATCH /api/auth/usuarios/<id>/      Actualizar usuario o rol (solo admin)
  DELETE /api/auth/usuarios/<id>/     Desactivar o borrar usuario (solo admin)
"""

import logging

from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.models import Permiso, Rol
from roles.permissions import requiere_permiso
from .models import PerfilUsuario
from .serializers import (
    ActualizarPerfilPropioSerializer,
    ActualizarUsuarioSerializer,
    LoginSerializer,
    RegistroPublicoSerializer,
    RegistroSerializer,
    UsuarioSerializer,
)

logger = logging.getLogger(__name__)

VeUsuarios = requiere_permiso('usuarios', 'ver')
CreaUsuarios = requiere_permiso('usuarios', 'crear')
EditaUsuarios = requiere_permiso('usuarios', 'editar')
EliminaUsuarios = requiere_permiso('usuarios', 'eliminar')


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
            PerfilUsuario.objects.filter(rol__codigo='admin').exists()
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
        data['rol'] = 'admin'

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
                    'email': {'type': 'string', 'example': 'admin@sayta.co'},
                    'password': {'type': 'string', 'example': 'contraseña123'},
                },
                'required': ['password'],
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
            rol = user.perfil.rol.codigo
            rol_display = user.perfil.rol.nombre
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

    @extend_schema(
        tags=['Auth'],
        summary='Actualizar perfil propio',
        description=(
            'Permite al usuario autenticado actualizar sus datos de perfil. '
            'Para cambiar `username`, `email` o `password_nueva` debe enviar '
            '`password_actual` correcta.'
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'example': 'maria.kogui'},
                    'email': {'type': 'string', 'example': 'maria@unimagdalena.edu.co'},
                    'first_name': {'type': 'string', 'example': 'María'},
                    'last_name': {'type': 'string', 'example': 'López'},
                    'etnia': {'type': 'string', 'enum': ['arhuaco', 'kogui'], 'example': 'kogui'},
                    'comunidad': {'type': 'string', 'example': 'Seykun'},
                    'password_actual': {'type': 'string', 'minLength': 1},
                    'password_nueva': {'type': 'string', 'minLength': 8},
                },
            }
        },
        responses={200: UsuarioSerializer, 400: OpenApiResponse(description='Datos inválidos')},
    )
    def patch(self, request):
        user = request.user
        serializer = ActualizarPerfilPropioSerializer(
            data=request.data,
            context={'user': user},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        password_nueva = data.pop('password_nueva', None)
        data.pop('password_actual', None)
        etnia = data.pop('etnia', None)
        comunidad = data.pop('comunidad', None)

        for field in ('username', 'email', 'first_name', 'last_name'):
            if field in data:
                setattr(user, field, data[field])

        if password_nueva:
            user.set_password(password_nueva)

        user.save()

        if etnia is not None or comunidad is not None:
            perfil = user.perfil
            update_fields = []
            if etnia is not None:
                perfil.etnia = etnia
                update_fields.append('etnia')
            if comunidad is not None:
                perfil.comunidad = comunidad
                update_fields.append('comunidad')
            update_fields.append('updated_at')
            perfil.save(update_fields=update_fields)

        user.refresh_from_db()
        logger.info('Perfil actualizado: %s', user.username)
        return Response(UsuarioSerializer(user).data)


class PermisosUsuarioView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auth'],
        summary='Permisos efectivos del usuario autenticado',
        description=(
            'Devuelve la foto actual del rol y permisos del usuario. El frontend '
            'puede llamar este endpoint después del login, al recargar la página, '
            'al volver a foco o cuando reciba un 403 para refrescar menús y acciones.'
        ),
        responses={200: OpenApiResponse(description='Permisos efectivos')},
    )
    def get(self, request):
        user = request.user
        try:
            rol = user.perfil.rol
        except PerfilUsuario.DoesNotExist:
            rol = None

        permisos_qs = Permiso.objects.none()
        if user.is_superuser:
            permisos_qs = Permiso.objects.filter(
                activo=True,
                modulo__activo=True,
            ).select_related('modulo', 'submodulo')
        elif rol and rol.activo:
            permisos_qs = Permiso.objects.filter(
                activo=True,
                modulo__activo=True,
                rol_permisos__rol=rol,
            ).select_related('modulo', 'submodulo')

        permisos_qs = permisos_qs.order_by('modulo__orden', 'submodulo__orden', 'codigo')

        permisos = []
        modulos = {}
        for permiso in permisos_qs:
            if permiso.submodulo_id:
                key = f'{permiso.modulo.codigo}.{permiso.submodulo.codigo}.{permiso.codigo}'
            else:
                key = f'{permiso.modulo.codigo}.{permiso.codigo}'
            permisos.append(key)

            modulo_data = modulos.setdefault(permiso.modulo.codigo, {
                'codigo': permiso.modulo.codigo,
                'nombre': permiso.modulo.nombre,
                'permisos': [],
                'submodulos': {},
            })

            permiso_data = {
                'id': permiso.id,
                'codigo': permiso.codigo,
                'nombre': permiso.nombre,
                'key': key,
            }
            if permiso.submodulo_id:
                submodulo_data = modulo_data['submodulos'].setdefault(permiso.submodulo.codigo, {
                    'codigo': permiso.submodulo.codigo,
                    'nombre': permiso.submodulo.nombre,
                    'permisos': [],
                })
                submodulo_data['permisos'].append(permiso_data)
            else:
                modulo_data['permisos'].append(permiso_data)

        modulos_payload = []
        for modulo_data in modulos.values():
            modulo_data['submodulos'] = list(modulo_data['submodulos'].values())
            modulos_payload.append(modulo_data)

        return Response({
            'usuario': UsuarioSerializer(user).data,
            'rol': {
                'id': rol.id,
                'codigo': rol.codigo,
                'nombre': rol.nombre,
                'activo': rol.activo,
            } if rol else None,
            'is_superuser': user.is_superuser,
            'permisos': permisos,
            'modulos': modulos_payload,
        })


# ──────────────────────────────────────────────────────────────────────────────
# Registro (admin)
# ──────────────────────────────────────────────────────────────────────────────

class RegistroView(APIView):
    permission_classes = [CreaUsuarios]

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
                    'etnia': {'type': 'string', 'enum': ['arhuaco', 'kogui'], 'example': 'kogui'},
                    'comunidad': {'type': 'string', 'example': 'Seykun'},
                    'rol': {
                        'type': 'string',
                        'enum': ['admin', 'desarrollador', 'investigador', 'anotador', 'consultor', 'colaborador_lengua', 'pendiente'],
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
# Auto-registro público — nace sin permisos, un admin le asigna el rol después
# ──────────────────────────────────────────────────────────────────────────────

class RegistroPublicoView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        tags=['Auth'],
        summary='Auto-registro público (sin token)',
        description=(
            'Cualquier persona puede crear su propia cuenta. Nace con el rol '
            '`pendiente`, que no tiene **ningún permiso** — no puede ver ni tocar '
            'ningún módulo hasta que un administrador le asigne un rol real desde '
            '`PATCH /api/auth/usuarios/<id>/`.\n\n'
            'Devuelve token de una vez para que la persona pueda entrar y consultar '
            '`GET /api/auth/perfil/` mientras espera la aprobación.'
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
                    'etnia': {'type': 'string', 'enum': ['arhuaco', 'kogui'], 'example': 'arhuaco'},
                    'comunidad': {'type': 'string', 'example': 'Nabusimake'},
                },
                'required': ['username', 'email', 'password'],
            }
        },
        responses={
            201: OpenApiResponse(description='Cuenta creada con rol "pendiente"'),
            400: OpenApiResponse(description='Datos inválidos o usuario ya existe'),
        },
        auth=[],
    )
    def post(self, request):
        serializer = RegistroPublicoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        logger.info('Auto-registro público: %s (rol pendiente)', user.username)
        return Response(
            {
                'mensaje': (
                    f'Cuenta "{user.username}" creada. Un administrador debe '
                    'asignarte un rol antes de que puedas usar el sistema.'
                ),
                'token': token.key,
                'usuario': UsuarioSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Gestión de usuarios (admin)
# ──────────────────────────────────────────────────────────────────────────────

class UsuariosListView(APIView):
    permission_classes = [VeUsuarios]

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
    _PERMISOS_POR_METODO = {'GET': VeUsuarios, 'PATCH': EditaUsuarios, 'DELETE': EliminaUsuarios}

    def get_permissions(self):
        permission_class = self._PERMISOS_POR_METODO.get(self.request.method, EditaUsuarios)
        return [permission_class()]

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
                    'username': {'type': 'string'},
                    'email': {'type': 'string'},
                    'first_name': {'type': 'string'},
                    'last_name': {'type': 'string'},
                    'rol': {'type': 'string', 'enum': ['admin', 'desarrollador', 'investigador', 'anotador', 'consultor', 'colaborador_lengua', 'pendiente']},
                    'etnia': {'type': 'string', 'enum': ['arhuaco', 'kogui']},
                    'comunidad': {'type': 'string'},
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
        etnia = data.pop('etnia', None)
        comunidad = data.pop('comunidad', None)

        for field, value in data.items():
            setattr(user, field, value)

        if password:
            user.set_password(password)

        user.save()

        if rol:
            rol_obj = Rol.objects.get(codigo=rol)
            perfil, created = PerfilUsuario.objects.get_or_create(
                usuario=user, defaults={'rol': rol_obj}
            )
            if not created:
                perfil.rol = rol_obj
                perfil.save(update_fields=['rol', 'updated_at'])
            # user.perfil quedó en caché de la consulta original (select_related)
            # con el rol viejo — refrescar para que la respuesta serializada
            # muestre el rol recién asignado, no el anterior.
            user.refresh_from_db()

        if etnia is not None or comunidad is not None:
            perfil = user.perfil
            update_fields = []
            if etnia is not None:
                perfil.etnia = etnia
                update_fields.append('etnia')
            if comunidad is not None:
                perfil.comunidad = comunidad
                update_fields.append('comunidad')
            update_fields.append('updated_at')
            perfil.save(update_fields=update_fields)
            user.refresh_from_db()

        logger.info('Usuario actualizado: %s por %s', user.username, request.user.username)
        return Response(UsuarioSerializer(user).data)

    @extend_schema(
        tags=['Auth — Administración'],
        summary='Desactivar o borrar un usuario',
        description=(
            'Por defecto suspende el acceso del usuario (`is_active=false`) y elimina '
            'su token. Para borrarlo definitivamente, enviar `?hard=true`. '
            'No permite desactivar ni borrar la propia cuenta autenticada.'
        ),
        parameters=[
            OpenApiParameter(
                name='hard',
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
                description='`true` para borrar definitivamente el usuario. Si se omite, solo lo desactiva.',
            ),
        ],
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
                {'error': 'No puedes desactivar ni borrar tu propia cuenta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        hard_delete = str(request.query_params.get('hard', '')).strip().lower() in (
            '1', 'true', 'si', 'sí', 'yes'
        )

        if hard_delete:
            username = user.username
            Token.objects.filter(user=user).delete()
            user.delete()
            logger.info('Usuario borrado definitivamente: %s por %s', username, request.user.username)
            return Response({'mensaje': f'Usuario "{username}" borrado definitivamente.'})

        user.is_active = False
        user.save(update_fields=['is_active'])
        # Invalidar token si existe
        Token.objects.filter(user=user).delete()

        logger.info('Usuario desactivado: %s por %s', user.username, request.user.username)
        return Response({'mensaje': f'Usuario "{user.username}" desactivado.'})
