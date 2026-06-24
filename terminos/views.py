"""
ViewSets del ecosistema de términos y embeddings.

Endpoints expuestos:
  GET/POST        /api/terminos/lenguas/
  GET/PUT/PATCH/DELETE /api/terminos/lenguas/{id}/

  GET/POST        /api/terminos/terminos-es/
  GET/PUT/PATCH/DELETE /api/terminos/terminos-es/{id}/

  GET/POST        /api/terminos/terminos/
  GET/PUT/PATCH/DELETE /api/terminos/terminos/{id}/
  POST            /api/terminos/terminos/carga-masiva/
  GET             /api/terminos/terminos/glosarios/

  GET             /api/terminos/embeddings/
  GET             /api/terminos/embeddings/{id}/
  POST            /api/terminos/embeddings/generar/
  POST            /api/terminos/embeddings/{id}/activar/
"""

import json
import logging

from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from usuarios.permissions import EsInvestigador
from .models import EmbeddingVersion, Lengua, TerminoEs, TerminoLeng
from .serializers import (
    CargaMasivaResponseSerializer,
    CargaMasivaSerializer,
    EmbeddingVersionSerializer,
    GenerarEmbeddingSerializer,
    LenguaSerializer,
    TerminoEsSerializer,
    TerminoLengCreateSerializer,
    TerminoLengSerializer,
)
from .services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


# Alias aceptados en el parámetro `codigos` del endpoint de exportación de
# glosarios; deben resolver a los mismos códigos canónicos usados en
# translator_api.views.COMMUNITY_ALIASES.
GLOSARIO_CODIGOS_ALIAS = {
    'kogui': 'kogui',
    'cogui': 'kogui',
    'arhuaco': 'arhuaco',
    'arhueco': 'arhuaco',
    'iku': 'arhuaco',
}


# ---------------------------------------------------------------------------
# Paginación estándar del proyecto
# ---------------------------------------------------------------------------


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


# ---------------------------------------------------------------------------
# Lenguas
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(
        tags=['Lenguas'],
        summary='Listar lenguas indígenas',
        description='Retorna todas las lenguas registradas con total de términos activos y embedding activo.',
        parameters=[
            OpenApiParameter('search', str, description='Buscar por nombre, código o descripción'),
            OpenApiParameter('ordering', str, description='Ordenar por: nombre, codigo, created_at'),
        ],
    ),
    create=extend_schema(
        tags=['Lenguas'],
        summary='Crear lengua indígena',
        examples=[
            OpenApiExample(
                'Ejemplo: Ette Taara',
                value={'codigo': 'ette', 'nombre': 'Ette Taara', 'descripcion': 'Lengua del pueblo Chimila'},
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(tags=['Lenguas'], summary='Detalle de una lengua'),
    update=extend_schema(tags=['Lenguas'], summary='Actualizar lengua completa'),
    partial_update=extend_schema(tags=['Lenguas'], summary='Actualizar campos de una lengua'),
    destroy=extend_schema(tags=['Lenguas'], summary='Eliminar lengua'),
)
class LenguaViewSet(viewsets.ModelViewSet):
    queryset = Lengua.objects.all()
    serializer_class = LenguaSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'codigo', 'descripcion']
    ordering_fields = ['nombre', 'codigo', 'created_at']
    ordering = ['nombre']



# ---------------------------------------------------------------------------
# Términos en español
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(
        tags=['Términos ES'],
        summary='Listar términos en español',
        parameters=[
            OpenApiParameter('search', str, description='Buscar por texto del término'),
        ],
    ),
    create=extend_schema(
        tags=['Términos ES'],
        summary='Crear término en español',
        examples=[
            OpenApiExample('Ejemplo', value={'termino': 'agua'}, request_only=True)
        ],
    ),
    retrieve=extend_schema(tags=['Términos ES'], summary='Detalle de un término en español'),
    update=extend_schema(tags=['Términos ES'], summary='Actualizar término en español'),
    partial_update=extend_schema(tags=['Términos ES'], summary='Actualizar parcialmente'),
    destroy=extend_schema(tags=['Términos ES'], summary='Eliminar término en español'),
)
class TerminoEsViewSet(viewsets.ModelViewSet):
    queryset = TerminoEs.objects.all()
    serializer_class = TerminoEsSerializer
    pagination_class = StandardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['termino']
    ordering_fields = ['termino', 'created_at']
    ordering = ['termino']



# ---------------------------------------------------------------------------
# Términos en lengua indígena
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(
        tags=['Términos Lengua'],
        summary='Listar términos en lengua indígena (paginado)',
        parameters=[
            OpenApiParameter('lengua', int, description='Filtrar por id de lengua'),
            OpenApiParameter('activo', bool, description='true = solo activos, false = solo inactivos'),
            OpenApiParameter('pos', str, description='Filtrar por parte del discurso (NOM, VRB, ADJ…)'),
            OpenApiParameter('search', str, description='Buscar en termino y definicion'),
            OpenApiParameter('termino_es_texto', str, description='Buscar por texto del término en español vinculado'),
            OpenApiParameter('ordering', str, description='Ordenar por: termino, created_at, updated_at'),
            OpenApiParameter('page', int, description='Número de página'),
            OpenApiParameter('page_size', int, description='Resultados por página (máx 200)'),
        ],
    ),
    create=extend_schema(
        tags=['Términos Lengua'],
        summary='Crear término en lengua indígena',
        examples=[
            OpenApiExample(
                'Ejemplo completo',
                value={
                    'termino': 'aabasu',
                    'lengua': 1,
                    'termino_es': None,
                    'definicion': 'nombre de hombre',
                    'pos': 'NOM_PR',
                    'sinonimos': [],
                    'ejemplos': ['aabasu naka mutu'],
                    'tipo_morfema': None,
                    'activo': True,
                },
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(tags=['Términos Lengua'], summary='Detalle de un término'),
    update=extend_schema(tags=['Términos Lengua'], summary='Actualizar término completo'),
    partial_update=extend_schema(tags=['Términos Lengua'], summary='Actualizar campos del término'),
    destroy=extend_schema(
        tags=['Términos Lengua'],
        summary='Desactivar término (soft delete)',
        description='No elimina el registro. Pone `activo = false`. Usar `/restaurar/` para reactivar.',
    ),
)
class TerminoLengViewSet(viewsets.ModelViewSet):
    """CRUD completo de términos en lengua indígena con paginación y filtros."""

    queryset = (
        TerminoLeng.objects.select_related('lengua', 'termino_es').all()
    )
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['lengua', 'activo', 'pos']
    search_fields = ['termino', 'definicion']
    ordering_fields = ['termino', 'created_at', 'updated_at']
    ordering = ['termino']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TerminoLengCreateSerializer
        return TerminoLengSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Filtro adicional por texto libre en termino_es
        termino_es = self.request.query_params.get('termino_es_texto')
        if termino_es:
            qs = qs.filter(termino_es__termino__icontains=termino_es)
        return qs

    def perform_destroy(self, instance):
        # Soft delete: no elimina, solo desactiva
        instance.activo = False
        instance.save(update_fields=['activo'])

    @extend_schema(
        tags=['Términos Lengua'],
        summary='Restaurar término desactivado',
        description='Reactiva un término que fue desactivado con DELETE. Pone `activo = true`.',
        responses={200: TerminoLengSerializer},
    )
    @action(detail=True, methods=['post'], url_path='restaurar')
    def restaurar(self, request, pk=None):
        termino = self.get_object()
        termino.activo = True
        termino.save(update_fields=['activo'])
        return Response(TerminoLengSerializer(termino).data)

    @extend_schema(
        tags=['Términos Lengua'],
        summary='Carga masiva de términos desde JSON',
        description=(
            'Carga cientos o miles de términos en una sola llamada.\n\n'
            '**Opción A — JSON body:**\n'
            '```json\n'
            '{"lengua_id": 1, "modo": "upsert", "terminos": [{...}]}\n'
            '```\n\n'
            '**Opción B — Archivo .json (multipart/form-data):**\n'
            'Campos: `archivo` (archivo .json), `lengua_id` (int), `modo` (string opcional).\n\n'
            '**Modos:** `upsert` (default) | `crear` | `actualizar`\n\n'
            'Los errores por fila no cancelan el resto de la operación.'
        ),
        request=CargaMasivaSerializer,
        responses={
            200: CargaMasivaResponseSerializer,
            207: CargaMasivaResponseSerializer,
            400: OpenApiResponse(description='Parámetros inválidos'),
            404: OpenApiResponse(description='Lengua no encontrada'),
        },
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'total': 3600,
                    'creados': 3200,
                    'actualizados': 350,
                    'sin_cambios': 40,
                    'errores': 10,
                    'detalle_errores': [
                        {'indice': 5, 'termino': 'xxx', 'error': 'El campo termino es obligatorio.'}
                    ],
                },
                response_only=True,
            )
        ],
    )
    @action(
        detail=False,
        methods=['post'],
        url_path='carga-masiva',
        parser_classes=[MultiPartParser, JSONParser],
    )
    def carga_masiva(self, request):
        """
        POST /api/terminos/terminos/carga-masiva/

        Carga masiva de términos desde JSON (body o archivo adjunto).

        --- Opción 1: JSON body ---
        Content-Type: application/json
        {
          "lengua_id": 1,
          "modo": "upsert",           // "crear" | "actualizar" | "upsert"  (default: upsert)
          "terminos": [
            {
              "termino": "aabasu",
              "definicion": "nombre de hombre",
              "pos": "NOM_PR",
              "sinonimos": [],
              "ejemplos": [],
              "tipo_morfema": null,
              "termino_es": "nombre propio"   // opcional: texto → busca/crea TerminoEs
            }
          ]
        }

        --- Opción 2: multipart/form-data con archivo .json ---
        Content-Type: multipart/form-data
        - archivo: <archivo.json>   (mismo esquema que "terminos" arriba)
        - lengua_id: 1
        - modo: upsert              (opcional)

        --- Respuesta ---
        {
          "total": 100,
          "creados": 80,
          "actualizados": 15,
          "sin_cambios": 3,
          "errores": 2,
          "detalle_errores": [
            {"indice": 5, "termino": "xxx", "error": "..."}
          ]
        }
        """
        # ---- 1. Extraer datos del request --------------------------------
        if request.content_type and 'multipart' in request.content_type:
            archivo = request.FILES.get('archivo')
            if not archivo:
                return Response(
                    {'error': 'Se requiere el campo "archivo" con un .json adjunto.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                datos_terminos = json.loads(archivo.read().decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                return Response(
                    {'error': f'El archivo no es JSON válido: {exc}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            lengua_id = request.data.get('lengua_id')
            modo = request.data.get('modo', 'upsert')
        else:
            body = request.data
            datos_terminos = body.get('terminos')
            lengua_id = body.get('lengua_id')
            modo = body.get('modo', 'upsert')

        # ---- 2. Validar parámetros globales ------------------------------
        if not lengua_id:
            return Response(
                {'error': 'Se requiere el campo "lengua_id".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(datos_terminos, list):
            return Response(
                {'error': '"terminos" debe ser una lista de objetos JSON.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if modo not in ('crear', 'actualizar', 'upsert'):
            return Response(
                {'error': '"modo" debe ser "crear", "actualizar" o "upsert".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lengua = Lengua.objects.get(pk=lengua_id)
        except Lengua.DoesNotExist:
            return Response(
                {'error': f'Lengua con id={lengua_id} no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---- 3. Procesar términos ----------------------------------------
        resultado = self._procesar_carga_masiva(datos_terminos, lengua, modo)
        http_status = status.HTTP_207_MULTI_STATUS if resultado['errores'] > 0 else status.HTTP_200_OK
        return Response(resultado, status=http_status)

    # ------------------------------------------------------------------
    # Helper privado para carga masiva
    # ------------------------------------------------------------------

    @staticmethod
    def _procesar_carga_masiva(datos: list, lengua, modo: str) -> dict:
        CAMPOS_ACTUALIZABLES = ['definicion', 'pos', 'sinonimos', 'ejemplos', 'tipo_morfema', 'termino_es_id', 'activo']

        # Pre-cargar todos los términos existentes de esta lengua en un dict
        existentes: dict[str, TerminoLeng] = {
            t.termino: t
            for t in TerminoLeng.objects.filter(lengua=lengua).select_related('termino_es')
        }

        # Cache de TerminoEs para no hacer un SELECT por fila
        cache_termino_es: dict[str, TerminoEs] = {}

        creados = 0
        actualizados = 0
        sin_cambios = 0
        errores = 0
        detalle_errores = []

        nuevos: list[TerminoLeng] = []
        a_actualizar: list[TerminoLeng] = []

        for idx, item in enumerate(datos):
            if not isinstance(item, dict):
                errores += 1
                detalle_errores.append({'indice': idx, 'termino': None, 'error': 'El elemento no es un objeto JSON.'})
                continue

            termino_str = (item.get('termino') or '').strip()
            if not termino_str:
                errores += 1
                detalle_errores.append({'indice': idx, 'termino': None, 'error': 'El campo "termino" es obligatorio.'})
                continue

            # Resolver TerminoEs si viene como texto
            termino_es_obj = None
            termino_es_texto = (item.get('termino_es') or '').strip()
            if termino_es_texto:
                if termino_es_texto not in cache_termino_es:
                    obj, _ = TerminoEs.objects.get_or_create(termino=termino_es_texto)
                    cache_termino_es[termino_es_texto] = obj
                termino_es_obj = cache_termino_es[termino_es_texto]

            campos = {
                'definicion': item.get('definicion', ''),
                'pos': item.get('pos', ''),
                'sinonimos': item.get('sinonimos') if isinstance(item.get('sinonimos'), list) else [],
                'ejemplos': item.get('ejemplos') if isinstance(item.get('ejemplos'), list) else [],
                'tipo_morfema': item.get('tipo_morfema'),
                'termino_es': termino_es_obj,
                'activo': item.get('activo', True),
            }

            ya_existe = termino_str in existentes

            try:
                if ya_existe:
                    if modo == 'crear':
                        sin_cambios += 1
                        continue

                    obj = existentes[termino_str]
                    cambio = False
                    for campo, valor in campos.items():
                        if getattr(obj, campo if campo != 'termino_es' else 'termino_es_id') != (
                            valor.id if campo == 'termino_es' and valor else valor
                        ):
                            setattr(obj, campo, valor)
                            cambio = True

                    if cambio:
                        a_actualizar.append(obj)
                    else:
                        sin_cambios += 1

                else:
                    if modo == 'actualizar':
                        sin_cambios += 1
                        continue

                    nuevos.append(TerminoLeng(termino=termino_str, lengua=lengua, **campos))

            except Exception as exc:
                errores += 1
                detalle_errores.append({'indice': idx, 'termino': termino_str, 'error': str(exc)})

        # ---- Persistir en bloque ----------------------------------------
        with transaction.atomic():
            if nuevos:
                TerminoLeng.objects.bulk_create(nuevos, batch_size=500, ignore_conflicts=False)
                creados = len(nuevos)

            if a_actualizar:
                TerminoLeng.objects.bulk_update(
                    a_actualizar,
                    fields=['definicion', 'pos', 'sinonimos', 'ejemplos', 'tipo_morfema', 'termino_es', 'activo'],
                    batch_size=500,
                )
                actualizados = len(a_actualizar)

        return {
            'total': len(datos),
            'creados': creados,
            'actualizados': actualizados,
            'sin_cambios': sin_cambios,
            'errores': errores,
            'detalle_errores': detalle_errores,
        }

    @extend_schema(
        tags=['Términos Lengua'],
        summary='Descargar glosarios kogui y arhuaco para revisión',
        description=(
            'Exporta los términos ya cargados en la base de datos para kogui y arhuaco '
            '(o las lenguas indicadas en `codigos`) en un único JSON diferenciado por lengua, '
            'con cabecera `Content-Disposition` para descargarlo directamente.\n\n'
            'Acepta alias: `kogui`/`cogui`, `arhuaco`/`arhueco`/`iku`.'
        ),
        parameters=[
            OpenApiParameter('codigos', str, description='Códigos de lengua separados por coma. Default: kogui,arhuaco'),
            OpenApiParameter('activo', bool, description='true = solo activos, false = solo inactivos. Si se omite, incluye todos'),
        ],
        responses={200: OpenApiResponse(description='JSON descargable: { "kogui": [...], "arhuaco": [...] }')},
        examples=[
            OpenApiExample(
                'Respuesta',
                value={
                    'kogui': [
                        {
                            'termino': 'Muñzek gue',
                            'definicion': 'Saludo matutino.',
                            'pos': 'FRS',
                            'termino_es': 'buenos días',
                            'sinonimos': [],
                            'ejemplos': [],
                            'tipo_morfema': None,
                            'activo': True,
                        }
                    ],
                    'arhuaco': [],
                },
                response_only=True,
            )
        ],
    )
    @action(detail=False, methods=['get'], url_path='glosarios')
    def glosarios(self, request):
        """
        GET /api/terminos/terminos/glosarios/?codigos=kogui,arhuaco&activo=true

        Exporta los términos por lengua en el mismo formato usado en carga-masiva,
        diferenciados por código de lengua, listo para descargar y revisar.
        """
        codigos_param = request.query_params.get('codigos', 'kogui,arhuaco')
        codigos_canonicos = []
        for crudo in codigos_param.split(','):
            crudo = crudo.strip().lower()
            if not crudo:
                continue
            canonico = GLOSARIO_CODIGOS_ALIAS.get(crudo, crudo)
            if canonico not in codigos_canonicos:
                codigos_canonicos.append(canonico)

        activo_param = request.query_params.get('activo')
        activo_filtro = None
        if activo_param is not None:
            activo_filtro = activo_param.strip().lower() in ('true', '1', 'si', 'sí')

        resultado = {}
        for codigo in codigos_canonicos:
            lengua = Lengua.objects.filter(codigo=codigo).first()
            if lengua is None:
                resultado[codigo] = []
                continue

            qs = TerminoLeng.objects.filter(lengua=lengua).select_related('termino_es').order_by('termino')
            if activo_filtro is not None:
                qs = qs.filter(activo=activo_filtro)

            resultado[codigo] = [
                {
                    'termino': t.termino,
                    'definicion': t.definicion,
                    'pos': t.pos,
                    'termino_es': t.termino_es.termino if t.termino_es else None,
                    'sinonimos': t.sinonimos,
                    'ejemplos': t.ejemplos,
                    'tipo_morfema': t.tipo_morfema,
                    'activo': t.activo,
                }
                for t in qs
            ]

        response = Response(resultado)
        response['Content-Disposition'] = 'attachment; filename="glosarios_kogui_arhuaco.json"'
        return response


# ---------------------------------------------------------------------------
# Versiones de Embeddings
# ---------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(
        tags=['Embeddings'],
        summary='Listar versiones de embeddings',
        description='Historial de todas las versiones por lengua. Filtrar con `?lengua=1&status=ready`.',
        parameters=[
            OpenApiParameter('lengua', int, description='Filtrar por id de lengua'),
            OpenApiParameter('status', str, description='pending | generating | ready | active | failed'),
            OpenApiParameter('is_active', bool, description='true = solo la versión activa'),
        ],
    ),
    retrieve=extend_schema(
        tags=['Embeddings'],
        summary='Detalle de una versión de embedding',
    ),
)
class EmbeddingVersionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Gestión de versiones de embeddings por lengua."""

    queryset = EmbeddingVersion.objects.select_related('lengua').all()
    serializer_class = EmbeddingVersionSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['lengua', 'status', 'is_active']
    ordering_fields = ['created_at', 'completed_at', 'num_terminos']
    ordering = ['-created_at']

    @extend_schema(
        tags=['Embeddings'],
        summary='Generar embeddings para una lengua (async)',
        description=(
            'Dispara la generación de embeddings en segundo plano. '
            'Retorna inmediatamente con un `task_id`. '
            'Consultar el estado con `GET /api/terminos/embeddings/estado/{task_id}/`.'
        ),
        request=GenerarEmbeddingSerializer,
        responses={
            202: OpenApiResponse(description='Generación iniciada', response=EmbeddingVersionSerializer),
            409: OpenApiResponse(description='Ya hay una generación en curso para esta lengua'),
            404: OpenApiResponse(description='Lengua no encontrada'),
        },
        examples=[
            OpenApiExample(
                'Body',
                value={'lengua_id': 1, 'model_name': 'intfloat/multilingual-e5-base'},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta 202',
                value={
                    'message': 'Generación iniciada en segundo plano.',
                    'task_id': '550e8400-e29b-41d4-a716-446655440000',
                    'embedding_version_id': '7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c',
                },
                response_only=True,
                status_codes=['202'],
            ),
        ],
    )
    @action(detail=False, methods=['post'], url_path='generar')
    def generar(self, request):
        """
        POST /api/terminos/embeddings/generar/

        Dispara la generación asíncrona de embeddings para una lengua.
        Retorna inmediatamente con el task_id y el id de la versión creada.

        Body: { "lengua_id": 1, "model_name": "intfloat/multilingual-e5-base" }
        """
        serializer = GenerarEmbeddingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lengua_id = serializer.validated_data['lengua_id']
        model_name = serializer.validated_data.get('model_name')

        try:
            Lengua.objects.get(pk=lengua_id)
        except Lengua.DoesNotExist:
            return Response(
                {'error': f'Lengua con id={lengua_id} no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verificar que no haya generación en curso para esta lengua
        en_curso = EmbeddingVersion.objects.filter(
            lengua_id=lengua_id,
            status__in=[EmbeddingVersion.STATUS_PENDING, EmbeddingVersion.STATUS_GENERATING],
        ).first()
        if en_curso:
            return Response(
                {
                    'error': 'Ya hay una generación en curso para esta lengua.',
                    'task_id': en_curso.task_id,
                    'status': en_curso.status,
                },
                status=status.HTTP_409_CONFLICT,
            )

        service = EmbeddingService()
        task_id = service.generar(lengua_id=lengua_id, model_name=model_name)

        ev = EmbeddingVersion.objects.get(task_id=task_id)
        return Response(
            {
                'message': 'Generación iniciada en segundo plano.',
                'task_id': task_id,
                'embedding_version_id': str(ev.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        tags=['Embeddings'],
        summary='Activar versión de embedding',
        description=(
            'Activa esta versión y desactiva la anterior para la misma lengua. '
            'El motor de búsqueda se recarga en caliente sin reiniciar el servidor. '
            'Solo se puede activar si el estado es `ready` o `active`.'
        ),
        responses={
            200: EmbeddingVersionSerializer,
            400: OpenApiResponse(description='Estado inválido para activar'),
            404: OpenApiResponse(description='Versión no encontrada'),
        },
    )
    @action(detail=True, methods=['post'], url_path='activar')
    def activar(self, request, pk=None):
        """
        POST /api/terminos/embeddings/{id}/activar/

        Activa esta versión de embedding y recarga el motor de búsqueda.
        Desactiva automáticamente la versión anteriormente activa de la misma lengua.
        """
        service = EmbeddingService()
        try:
            ev = service.activar(pk)
        except EmbeddingVersion.DoesNotExist:
            return Response({'error': 'Versión no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(EmbeddingVersionSerializer(ev).data)

    @extend_schema(
        tags=['Embeddings'],
        summary='Consultar estado de generación',
        description=(
            'Polling del estado de una tarea de generación de embeddings. '
            'Estados: `pending` → `generating` → `ready` (o `failed`).'
        ),
        parameters=[
            OpenApiParameter('task_id', str, location=OpenApiParameter.PATH, description='UUID del task_id retornado por /generar/'),
        ],
        responses={
            200: EmbeddingVersionSerializer,
            404: OpenApiResponse(description='task_id no encontrado'),
        },
    )
    @action(detail=False, methods=['get'], url_path='estado/(?P<task_id>[^/.]+)')
    def estado(self, request, task_id=None):
        """
        GET /api/terminos/embeddings/estado/{task_id}/

        Retorna el estado actual de una tarea de generación.
        """
        try:
            ev = EmbeddingVersion.objects.select_related('lengua').get(task_id=task_id)
        except EmbeddingVersion.DoesNotExist:
            return Response(
                {'error': f'No se encontró tarea con task_id={task_id}'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(EmbeddingVersionSerializer(ev).data)
