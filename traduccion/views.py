"""
App de traducción texto-a-texto usando embeddings semánticos.

Endpoint:
  POST /api/traduccion/traducir/
  Body: {"texto": "...", "lengua_id": 1, "direccion": "es_a_lengua"}

Flujo:
  1. Resuelve la Lengua y su EmbeddingVersion activa.
  2. Usa la dirección enviada por el cliente para etiquetar la respuesta.
  3. Busca los 3 términos más cercanos en el índice FAISS de esa lengua.
  4. Devuelve termino + definicion + score para cada resultado.
"""

import logging

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TraducirRequestSerializer, TraducirResponseSerializer

logger = logging.getLogger(__name__)


def _formatear_direccion(direccion: str, lengua_codigo: str) -> str:
    if direccion == 'es_a_lengua':
        return f'es→{lengua_codigo}'
    return f'{lengua_codigo}→es'


class TraducirView(APIView):

    @extend_schema(
        tags=['Traducción'],
        summary='Traducir texto usando embeddings semánticos',
        description=(
            'Recibe un texto, el ID de la lengua indígena y la **dirección** de traducción.\n\n'
            '- `es_a_lengua`: el texto está en español → se busca el equivalente en la lengua indígena.\n'
            '- `lengua_a_es`: el texto está en la lengua indígena → se busca su equivalente en español.\n\n'
            'Retorna los **3 términos más cercanos** del glosario con su definición '
            'y un score de similitud coseno (0–1).\n\n'
            '**Requisito:** la lengua debe tener un embedding en estado `active`. '
            'Generarlo con `POST /api/terminos/embeddings/generar/` y activarlo con '
            '`POST /api/terminos/embeddings/{id}/activar/`.'
        ),
        request=TraducirRequestSerializer,
        responses={
            200: TraducirResponseSerializer,
            400: OpenApiResponse(description='Parámetros inválidos o faltantes'),
            404: OpenApiResponse(description='Lengua no encontrada'),
            422: OpenApiResponse(description='La lengua no tiene embedding activo'),
            500: OpenApiResponse(description='Error interno en búsqueda semántica'),
        },
        examples=[
            OpenApiExample(
                'Español → Arhuaco',
                value={'texto': 'agua', 'lengua_id': 1, 'direccion': 'es_a_lengua'},
                request_only=True,
            ),
            OpenApiExample(
                'Arhuaco → Español',
                value={'texto': 'zaku', 'lengua_id': 1, 'direccion': 'lengua_a_es'},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'texto_entrada': 'agua',
                    'lengua': {'id': 1, 'codigo': 'iku', 'nombre': 'Arhuaco'},
                    'embedding': {
                        'version_id': '7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c',
                        'version': '20241201_123456',
                        'modelo': 'intfloat/multilingual-e5-base',
                        'num_terminos': 3600,
                    },
                    'direccion': 'es→iku',
                    'resultados': [
                        {'termino': 'zaku', 'definicion': 'agua del río', 'score': 0.9231},
                        {'termino': 'zaku naka', 'definicion': 'corriente de agua', 'score': 0.8912},
                        {'termino': 'amu', 'definicion': 'lluvia, agua del cielo', 'score': 0.8745},
                    ],
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def post(self, request):
        serializer = TraducirRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        texto = serializer.validated_data['texto'].strip()
        lengua_id = serializer.validated_data['lengua_id']
        direccion_input = serializer.validated_data['direccion']

        # --- Resolver lengua y embedding activo ---
        try:
            from terminos.models import EmbeddingVersion, Lengua
            lengua = Lengua.objects.get(pk=lengua_id)
        except Lengua.DoesNotExist:
            return Response(
                {'error': f'Lengua con id={lengua_id} no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        embedding_activo = (
            EmbeddingVersion.objects
            .filter(lengua=lengua, status=EmbeddingVersion.STATUS_ACTIVE)
            .first()
        )
        if embedding_activo is None:
            return Response(
                {
                    'error': (
                        f'La lengua "{lengua.nombre}" no tiene un embedding activo. '
                        'Genera uno con POST /api/terminos/embeddings/generar/ '
                        'y actívalo con POST /api/terminos/embeddings/{id}/activar/.'
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # --- Búsqueda semántica ---
        try:
            from translator_api.search_engine import MultiLanguageSearchEngine
            engine = MultiLanguageSearchEngine.get_instance()
            hits = engine.search(texto, language_code=lengua.codigo, top_k=3)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as exc:
            logger.error('Error en búsqueda semántica: %s', exc, exc_info=True)
            return Response({'error': f'Error interno: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        resultados = [
            {
                'termino': h.get('lemma'),
                'definicion': h.get('definicion') or '',
                'score': round(h['score'], 4) if h.get('score') is not None else None,
            }
            for h in hits
        ]

        data = {
            'texto_entrada': texto,
            'lengua': {
                'id': lengua.id,
                'codigo': lengua.codigo,
                'nombre': lengua.nombre,
            },
            'embedding': {
                'version_id': str(embedding_activo.id),
                'version': embedding_activo.version,
                'modelo': embedding_activo.model_name,
                'num_terminos': embedding_activo.num_terminos,
            },
            'direccion': _formatear_direccion(direccion_input, lengua.codigo),
            'resultados': resultados,
        }
        return Response(TraducirResponseSerializer(data).data)

    @extend_schema(
        tags=['Traducción'],
        summary='Información del endpoint de traducción',
        responses={200: OpenApiResponse(description='Descripción y ejemplo de uso')},
    )
    def get(self, request):
        return Response({
            'descripcion': 'Envía texto, lengua_id y direccion vía POST.',
            'direcciones_disponibles': {
                'es_a_lengua': 'texto en español → busca en la lengua indígena',
                'lengua_a_es': 'texto en lengua indígena → busca equivalente en español',
            },
            'ejemplo': {'texto': 'agua', 'lengua_id': 1, 'direccion': 'es_a_lengua'},
        })
