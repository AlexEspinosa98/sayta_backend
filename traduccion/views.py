"""
App de traducción texto-a-texto usando embeddings semánticos.

Endpoint:
  POST /api/traduccion/traducir/
  Body: {"texto": "...", "lengua_id": 1, "direccion": "es_a_lengua"}

Flujo:
  1. Resuelve la Lengua y su EmbeddingVersion activa.
  2. Ejecuta el pipeline multi-estrategia (frase completa → n-gramas → tokens).
  3. Enriquece resultados con termino_es desde BD si el metadata no lo tiene.
  4. Devuelve los 3 términos más cercanos con termino, termino_es, definicion y score.
"""

import logging

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .pipeline import TranslationPipeline
from .serializers import TraducirRequestSerializer, TraducirResponseSerializer

logger = logging.getLogger(__name__)


def _formatear_direccion(direccion: str, lengua_codigo: str) -> str:
    if direccion == 'es_a_lengua':
        return f'es→{lengua_codigo}'
    return f'{lengua_codigo}→es'


class TraducirView(APIView):

    @extend_schema(
        tags=['Traducción'],
        summary='Traducir texto usando embeddings semánticos (multi-palabra)',
        description=(
            'Recibe un texto, el ID de la lengua indígena y la **dirección** de traducción.\n\n'
            '**Dirección:**\n'
            '- `es_a_lengua` → texto en español, busca términos en la lengua indígena.\n'
            '- `lengua_a_es` → texto en lengua indígena, busca su equivalente en español.\n\n'
            '**Análisis multi-estrategia:** el pipeline ejecuta tres niveles de búsqueda '
            'para cubrir tanto palabras simples como frases compuestas del glosario:\n'
            '1. **Frase completa** — busca el texto tal como llega (peso 1.0).\n'
            '2. **N-gramas** — prueba todas las combinaciones de bi y tri-gramas (peso 0.92).\n'
            '3. **Tokens individuales** — busca cada palabra por separado (peso 0.80).\n\n'
            'Los resultados de los tres niveles se fusionan por término y se retornan '
            'los **3 más cercanos** ordenados por score.\n\n'
            'Cada resultado incluye `termino` (lengua indígena), `termino_es` (español), '
            '`definicion` y `coincidencia` (sub-consulta que lo encontró).\n\n'
            '**Requisito:** la lengua debe tener un embedding en estado `active`.'
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
                'Palabra simple — Español → Arhuaco',
                value={'texto': 'jaguar', 'lengua_id': 1, 'direccion': 'es_a_lengua'},
                request_only=True,
            ),
            OpenApiExample(
                'Frase compuesta — Arhuaco → Español',
                value={'texto': 'Du zari bunsi chano', 'lengua_id': 1, 'direccion': 'lengua_a_es'},
                request_only=True,
            ),
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'texto_entrada': 'Du zari bunsi chano',
                    'lengua': {'id': 1, 'codigo': 'iku', 'nombre': 'Arhuaco'},
                    'embedding': {
                        'version_id': '7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c',
                        'version': '20260527_100000',
                        'modelo': 'intfloat/multilingual-e5-base',
                        'num_terminos': 197,
                    },
                    'direccion': 'iku→es',
                    'resultados': [
                        {
                            'termino': 'Du zari bunsi chano',
                            'termino_es': 'buenos días',
                            'definicion': 'Saludo de la mañana en lengua ikʉn.',
                            'score': 0.9801,
                            'coincidencia': 'Du zari bunsi chano',
                        },
                        {
                            'termino': 'Du zari ɉwi nayo',
                            'termino_es': 'buenas tardes',
                            'definicion': 'Saludo de la tarde en lengua ikʉn.',
                            'score': 0.8740,
                            'coincidencia': 'Du zari',
                        },
                        {
                            'termino': 'Bunachʉn',
                            'termino_es': 'español',
                            'definicion': 'Nombre del español o castellano en lengua ikʉn.',
                            'score': 0.7120,
                            'coincidencia': 'chano',
                        },
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

        # --- Pipeline multi-estrategia ---
        try:
            from translator_api.search_engine import MultiLanguageSearchEngine
            engine = MultiLanguageSearchEngine.get_instance()
            pipeline = TranslationPipeline(engine, language_code=lengua.codigo)
            resultados = pipeline.translate(texto, top_k=3)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as exc:
            logger.error('Error en pipeline de traducción: %s', exc, exc_info=True)
            return Response(
                {'error': f'Error interno en traducción: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        mejor = resultados[0] if resultados else None
        conclusion = {
            'termino': mejor['termino'],
            'termino_es': mejor['termino_es'],
            'definicion': mejor['definicion'],
            'probabilidad': mejor['probabilidad'],
        } if mejor else None

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
            'conclusion': conclusion,
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
                'lengua_a_es': 'texto en lengua indígena → busca su equivalente en español',
            },
            'ejemplo': {'texto': 'Du zari bunsi chano', 'lengua_id': 1, 'direccion': 'lengua_a_es'},
        })
