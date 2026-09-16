"""
Módulo de administración dinámico — gestionar módulos, permisos y roles vía API.

Todos los endpoints requieren el permiso 'usuarios.gestionar_roles' (solo lo
tiene el rol 'admin' por semilla).
"""

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Modulo, Permiso, Rol, RolPermiso
from .permissions import requiere_permiso
from .serializers import (
    AsignarPermisosSerializer,
    ModuloCreateSerializer,
    ModuloSerializer,
    PermisoCreateSerializer,
    PermisoSerializer,
    RolCreateSerializer,
    RolSerializer,
)

logger = logging.getLogger(__name__)

ADMIN_MODULO = 'usuarios'
ADMIN_ACCION = 'gestionar_roles'

NOTA_DINAMISMO = (
    'Crear una sección o permiso aquí no activa control de acceso por sí solo: '
    'un desarrollador debe cablear requiere_permiso(...) en la vista real. '
    'Lo que sí es 100% dinámico sin tocar código: crear roles nuevos y decidir '
    'qué permisos ya existentes tiene cada uno.'
)


# ---------------------------------------------------------------------------
# Módulos (secciones)
# ---------------------------------------------------------------------------

class ModuloListCreateView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    @extend_schema(
        tags=['Admin — Módulos'],
        summary='Listar secciones del sistema',
        responses={200: ModuloSerializer(many=True)},
    )
    def get(self, request):
        modulos = Modulo.objects.prefetch_related('permisos').all()
        return Response({
            'nota': NOTA_DINAMISMO,
            'modulos': ModuloSerializer(modulos, many=True).data,
        })

    @extend_schema(
        tags=['Admin — Módulos'],
        summary='Crear sección nueva',
        request=ModuloCreateSerializer,
        responses={201: ModuloSerializer},
    )
    def post(self, request):
        serializer = ModuloCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        modulo = serializer.save()
        logger.info('Módulo creado: %s por %s', modulo.codigo, request.user.username)
        return Response(ModuloSerializer(modulo).data, status=status.HTTP_201_CREATED)


class ModuloDetailView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    def _get(self, pk):
        return Modulo.objects.filter(pk=pk).first()

    @extend_schema(
        tags=['Admin — Módulos'],
        summary='Editar sección',
        request=ModuloCreateSerializer,
        responses={200: ModuloSerializer, 404: OpenApiResponse(description='Módulo no encontrado')},
    )
    def patch(self, request, pk):
        modulo = self._get(pk)
        if not modulo:
            return Response({'error': 'Módulo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ModuloCreateSerializer(modulo, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(ModuloSerializer(modulo).data)

    @extend_schema(
        tags=['Admin — Módulos'],
        summary='Desactivar sección',
        responses={200: OpenApiResponse(description='Módulo desactivado'), 404: OpenApiResponse(description='Módulo no encontrado')},
    )
    def delete(self, request, pk):
        modulo = self._get(pk)
        if not modulo:
            return Response({'error': 'Módulo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        modulo.activo = False
        modulo.save(update_fields=['activo'])
        return Response({'mensaje': f'Módulo "{modulo.codigo}" desactivado.'})


class ModuloPermisosView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    @extend_schema(
        tags=['Admin — Módulos'],
        summary='Crear acción/permiso dentro de una sección',
        request=PermisoCreateSerializer,
        responses={201: PermisoSerializer, 404: OpenApiResponse(description='Módulo no encontrado')},
    )
    def post(self, request, pk):
        modulo = Modulo.objects.filter(pk=pk).first()
        if not modulo:
            return Response({'error': 'Módulo no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PermisoCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        codigo = serializer.validated_data['codigo']
        if Permiso.objects.filter(modulo=modulo, codigo=codigo).exists():
            return Response(
                {'error': f'Ya existe el permiso "{codigo}" en el módulo "{modulo.codigo}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        permiso = serializer.save(modulo=modulo)
        logger.info('Permiso creado: %s.%s por %s', modulo.codigo, permiso.codigo, request.user.username)
        return Response(PermisoSerializer(permiso).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class RolListCreateView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    @extend_schema(
        tags=['Admin — Roles'],
        summary='Listar roles',
        responses={200: RolSerializer(many=True)},
    )
    def get(self, request):
        roles = Rol.objects.all()
        return Response(RolSerializer(roles, many=True).data)

    @extend_schema(
        tags=['Admin — Roles'],
        summary='Crear rol nuevo',
        description='El rol nace con `es_sistema=False`: se puede editar y borrar libremente si no tiene usuarios asignados.',
        request=RolCreateSerializer,
        responses={201: RolSerializer},
    )
    def post(self, request):
        serializer = RolCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        rol = serializer.save(es_sistema=False)
        logger.info('Rol creado: %s por %s', rol.codigo, request.user.username)
        return Response(RolSerializer(rol).data, status=status.HTTP_201_CREATED)


class RolDetailView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    def _get(self, pk):
        return Rol.objects.filter(pk=pk).first()

    @extend_schema(tags=['Admin — Roles'], summary='Detalle de un rol', responses={200: RolSerializer})
    def get(self, request, pk):
        rol = self._get(pk)
        if not rol:
            return Response({'error': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(RolSerializer(rol).data)

    @extend_schema(tags=['Admin — Roles'], summary='Editar rol', request=RolCreateSerializer, responses={200: RolSerializer})
    def patch(self, request, pk):
        rol = self._get(pk)
        if not rol:
            return Response({'error': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if rol.es_sistema and 'codigo' in request.data and request.data['codigo'] != rol.codigo:
            return Response(
                {'error': 'No se puede cambiar el código de un rol de sistema.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RolCreateSerializer(rol, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(RolSerializer(rol).data)

    @extend_schema(
        tags=['Admin — Roles'],
        summary='Eliminar rol',
        description='Bloqueado si el rol es de sistema o tiene usuarios asignados (reasígnalos primero).',
        responses={200: OpenApiResponse(description='Rol eliminado'), 400: OpenApiResponse(description='No se puede eliminar')},
    )
    def delete(self, request, pk):
        rol = self._get(pk)
        if not rol:
            return Response({'error': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if rol.es_sistema:
            return Response(
                {'error': 'No se puede eliminar un rol de sistema. Desactívalo en su lugar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if rol.perfiles.exists():
            return Response(
                {'error': 'Este rol tiene usuarios asignados. Reasígnalos antes de eliminarlo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        codigo = rol.codigo
        rol.delete()
        logger.info('Rol eliminado: %s por %s', codigo, request.user.username)
        return Response({'mensaje': f'Rol "{codigo}" eliminado.'})


class RolPermisosView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    @extend_schema(
        tags=['Admin — Roles'],
        summary='Ver permisos asignados a un rol',
        responses={200: PermisoSerializer(many=True)},
    )
    def get(self, request, pk):
        rol = Rol.objects.filter(pk=pk).first()
        if not rol:
            return Response({'error': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        permisos = Permiso.objects.filter(rol_permisos__rol=rol).select_related('modulo')
        return Response(PermisoSerializer(permisos, many=True).data)

    @extend_schema(
        tags=['Admin — Roles'],
        summary='Reemplazar el set completo de permisos de un rol',
        description='Idempotente: la lista enviada reemplaza por completo la asignación anterior.',
        request=AsignarPermisosSerializer,
        responses={200: PermisoSerializer(many=True)},
    )
    def put(self, request, pk):
        rol = Rol.objects.filter(pk=pk).first()
        if not rol:
            return Response({'error': 'Rol no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AsignarPermisosSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        permiso_ids = serializer.validated_data['permiso_ids']
        RolPermiso.objects.filter(rol=rol).delete()
        RolPermiso.objects.bulk_create([
            RolPermiso(rol=rol, permiso_id=pid) for pid in permiso_ids
        ])
        logger.info(
            'Permisos actualizados para rol %s (%d permisos) por %s',
            rol.codigo, len(permiso_ids), request.user.username,
        )
        permisos = Permiso.objects.filter(rol_permisos__rol=rol).select_related('modulo')
        return Response(PermisoSerializer(permisos, many=True).data)


class MatrizView(APIView):
    permission_classes = [requiere_permiso(ADMIN_MODULO, ADMIN_ACCION)]

    @extend_schema(
        tags=['Admin — Roles'],
        summary='Matriz completa módulos × roles × permisos',
        description='Pensada para pintar una tabla de administración en un futuro frontend.',
    )
    def get(self, request):
        modulos = Modulo.objects.filter(activo=True).prefetch_related('permisos')
        roles = Rol.objects.filter(activo=True)
        asignados = set(RolPermiso.objects.values_list('rol_id', 'permiso_id'))

        data = []
        for modulo in modulos:
            permisos_data = []
            for permiso in modulo.permisos.all():
                permisos_data.append({
                    'permiso': permiso.codigo,
                    'permiso_id': permiso.id,
                    'nombre': permiso.nombre,
                    'roles': {
                        rol.codigo: (rol.id, permiso.id) in asignados
                        for rol in roles
                    },
                })
            data.append({
                'modulo': modulo.codigo,
                'nombre': modulo.nombre,
                'permisos': permisos_data,
            })

        return Response({
            'roles': [{'id': r.id, 'codigo': r.codigo, 'nombre': r.nombre} for r in roles],
            'modulos': data,
        })
