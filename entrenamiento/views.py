"""
Módulo de entrenamiento de modelos ASR para lenguas indígenas.

Endpoints:
  GET  /api/entrenamiento/modelos-disponibles/             Catálogo curado de modelos HF
  GET  /api/entrenamiento/modelos/                         Modelos descargados
  POST /api/entrenamiento/modelos/descargar/               Descarga un modelo desde HF Hub
  GET  /api/entrenamiento/dataset/                         Stats de datos etiquetados por comunidad
  GET  /api/entrenamiento/dataset/<community>/             Stats detallados de una comunidad
  POST /api/entrenamiento/entrenar/                        Lanza fine-tuning (asíncrono)
  GET  /api/entrenamiento/experimentos/                    Lista experimentos
  GET  /api/entrenamiento/experimentos/<id>/               Detalle de un experimento
  GET  /api/entrenamiento/experimentos/<id>/estado/        Estado en tiempo real
  POST /api/entrenamiento/experimentos/<id>/activar/       Activa el modelo entrenado
  POST /api/entrenamiento/transcribir/                     Transcribe audio con el modelo activo
  POST /api/entrenamiento/transcribir-y-traducir/          Transcribe + traduce
"""

import logging
import os
import tempfile
from pathlib import Path

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ExperimentoEntrenamiento, ModeloAudio
from .serializers import (
    EntrenarRequestSerializer,
    ExperimentoDetailSerializer,
    ExperimentoListSerializer,
    ModeloAudioSerializer,
    TranscribirRequestSerializer,
    TranscribirTraducirRequestSerializer,
)
from .services import dataset_service, model_service, training_service

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS_PERMITIDAS = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.mp4'}


# ======================================================================
# Catálogo de modelos
# ======================================================================

class ModelosDisponiblesView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Modelos'],
        summary='Catálogo de modelos HuggingFace recomendados para ASR',
        description=(
            'Lista de modelos abiertos en HuggingFace adecuados para fine-tuning '
            'en lenguas indígenas colombianas. Incluye Whisper y Wav2Vec2.'
        ),
        responses={200: OpenApiResponse(description='Lista de modelos disponibles con metadatos')},
    )
    def get(self, request):
        catalogo = []
        for m in model_service.CATALOGO:
            entry = dict(m)
            entry['descargado'] = model_service.is_downloaded(m['nombre_hf'])
            try:
                db_model = ModeloAudio.objects.filter(nombre_hf=m['nombre_hf']).first()
                entry['id_bd'] = db_model.id if db_model else None
            except Exception:
                entry['id_bd'] = None
            catalogo.append(entry)

        return Response({'total': len(catalogo), 'modelos': catalogo})


# ======================================================================
# Gestión de modelos descargados
# ======================================================================

class ModeloListView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Modelos'],
        summary='Lista de modelos ASR descargados localmente',
        responses={200: ModeloAudioSerializer(many=True)},
    )
    def get(self, request):
        qs = ModeloAudio.objects.all()
        serializer = ModeloAudioSerializer(qs, many=True)
        return Response({'total': qs.count(), 'modelos': serializer.data})


class ModeloDescargarView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Modelos'],
        summary='Descargar un modelo desde HuggingFace Hub',
        description=(
            'Descarga el modelo y su procesador al disco local. '
            'Puede tardar varios minutos dependiendo del tamaño. '
            'La llamada es **síncrona** — espera hasta que la descarga termine.'
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'nombre_hf': {'type': 'string', 'example': 'openai/whisper-small'},
                    'tipo': {'type': 'string', 'enum': ['whisper', 'wav2vec2']},
                    'descripcion': {'type': 'string'},
                },
                'required': ['nombre_hf', 'tipo'],
            }
        },
        responses={
            200: OpenApiResponse(description='Modelo ya descargado'),
            201: OpenApiResponse(description='Modelo descargado exitosamente'),
            400: OpenApiResponse(description='Parámetros inválidos'),
            500: OpenApiResponse(description='Error durante la descarga'),
        },
        examples=[
            OpenApiExample(
                'Whisper Small',
                value={'nombre_hf': 'openai/whisper-small', 'tipo': 'whisper'},
                request_only=True,
            ),
            OpenApiExample(
                'Wav2Vec2 XLSR',
                value={'nombre_hf': 'facebook/wav2vec2-large-xlsr-53', 'tipo': 'wav2vec2'},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        nombre_hf = request.data.get('nombre_hf', '').strip()
        tipo = request.data.get('tipo', '').strip()
        descripcion = request.data.get('descripcion', '').strip()

        if not nombre_hf or not tipo:
            return Response(
                {'error': "Faltan campos 'nombre_hf' y/o 'tipo'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if tipo not in ('whisper', 'wav2vec2'):
            return Response(
                {'error': "El campo 'tipo' debe ser 'whisper' o 'wav2vec2'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Si ya está en BD y descargado
        existing = ModeloAudio.objects.filter(nombre_hf=nombre_hf).first()
        if existing and existing.descargado and model_service.is_downloaded(nombre_hf):
            return Response(
                {
                    'mensaje': 'El modelo ya está descargado.',
                    'modelo': ModeloAudioSerializer(existing).data,
                },
                status=status.HTTP_200_OK,
            )

        result = model_service.download_model(nombre_hf, tipo)
        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        modelo, _ = ModeloAudio.objects.update_or_create(
            nombre_hf=nombre_hf,
            defaults={
                'tipo': tipo,
                'descripcion': descripcion,
                'ruta_local': result['ruta_local'],
                'descargado': True,
            },
        )
        return Response(
            {'mensaje': result['mensaje'], 'modelo': ModeloAudioSerializer(modelo).data},
            status=status.HTTP_201_CREATED,
        )


# ======================================================================
# Dataset — estadísticas de datos etiquetados
# ======================================================================

class DatasetEstadoView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Dataset'],
        summary='Estadísticas de datos etiquetados disponibles por comunidad',
        description=(
            'Muestra cuántos audios etiquetados hay por comunidad (Arhuaco, Kogui, etc.), '
            'cuántos están listos para entrenar y el porcentaje de completitud.'
        ),
        responses={200: OpenApiResponse(description='Resumen de dataset por comunidad')},
    )
    def get(self, request):
        stats = dataset_service.get_dataset_stats()
        return Response(stats)


class DatasetComunidadView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Dataset'],
        summary='Estadísticas detalladas por jornada de una comunidad',
        responses={
            200: OpenApiResponse(description='Detalle de muestras por jornada/sesión'),
            404: OpenApiResponse(description='Comunidad no encontrada'),
        },
    )
    def get(self, request, community: str):
        stats = dataset_service.get_community_stats(community)
        if stats is None:
            return Response(
                {'error': f"Comunidad '{community}' no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(stats)


# ======================================================================
# Entrenamiento
# ======================================================================

class EntrenarView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Lanzar fine-tuning de un modelo ASR (asíncrono)',
        description=(
            'Dispara el entrenamiento en segundo plano. Retorna inmediatamente con el '
            '`id` del experimento. Monitorea el estado con '
            '`GET /api/entrenamiento/experimentos/{id}/estado/`.\n\n'
            '**Config opcionales:**\n'
            '- `num_train_epochs` (int, default 20)\n'
            '- `learning_rate` (float, default 1e-4 para wav2vec2 / 1e-5 para whisper)\n'
            '- `per_device_train_batch_size` (int, default 4)\n'
            '- `gradient_accumulation_steps` (int, default 2)\n'
            '- `warmup_steps` (int, default 100)\n'
            '- `use_peft` (bool, default false) — LoRA para fine-tuning eficiente\n'
            '- `peft_r` (int, default 16)\n'
            '- `whisper_language` (str, default "es")\n'
            '- `mlflow_tracking_uri` (str) — URI del servidor MLflow\n'
        ),
        request=EntrenarRequestSerializer,
        responses={
            202: OpenApiResponse(description='Entrenamiento iniciado (asíncrono)'),
            400: OpenApiResponse(description='Parámetros inválidos'),
            404: OpenApiResponse(description='Lengua o modelo no encontrados'),
            422: OpenApiResponse(description='Datos insuficientes para entrenar'),
        },
        examples=[
            OpenApiExample(
                'Fine-tuning Whisper Small — Arhuaco',
                value={
                    'nombre': 'whisper-small-iku-v1',
                    'lengua_id': 1,
                    'modelo_audio_id': 1,
                    'comunidades': ['arhuaco'],
                    'config': {
                        'num_train_epochs': 20,
                        'learning_rate': 1e-5,
                        'per_device_train_batch_size': 4,
                        'use_peft': False,
                        'whisper_language': 'es',
                    },
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = EntrenarRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # Resolver Lengua
        try:
            from terminos.models import Lengua
            lengua = Lengua.objects.get(pk=data['lengua_id'])
        except Lengua.DoesNotExist:
            return Response(
                {'error': f"Lengua id={data['lengua_id']} no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Resolver ModeloAudio
        try:
            modelo_audio = ModeloAudio.objects.get(pk=data['modelo_audio_id'])
        except ModeloAudio.DoesNotExist:
            return Response(
                {'error': f"Modelo de audio id={data['modelo_audio_id']} no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not modelo_audio.descargado or not model_service.is_downloaded(modelo_audio.nombre_hf):
            return Response(
                {
                    'error': (
                        f'El modelo "{modelo_audio.nombre_hf}" no está descargado. '
                        'Descárgalo primero con POST /api/entrenamiento/modelos/descargar/'
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Verificar que ya no haya un entrenamiento activo para esta lengua y modelo
        entrenando = ExperimentoEntrenamiento.objects.filter(
            lengua=lengua,
            modelo_base=modelo_audio,
            estado=ExperimentoEntrenamiento.ESTADO_ENTRENANDO,
        ).exists()
        if entrenando:
            return Response(
                {'error': 'Ya hay un entrenamiento en curso para esta lengua y modelo.'},
                status=status.HTTP_409_CONFLICT,
            )

        # Construir dataset
        samples = dataset_service.build_samples(data['comunidades'])
        if len(samples) < dataset_service.MIN_MUESTRAS_ENTRENAMIENTO:
            return Response(
                {
                    'error': (
                        f'Se necesitan al menos {dataset_service.MIN_MUESTRAS_ENTRENAMIENTO} '
                        f'muestras etiquetadas. Solo se encontraron {len(samples)}. '
                        'Etiqueta más audios antes de entrenar.'
                    ),
                    'muestras_encontradas': len(samples),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Crear experimento en BD
        exp = ExperimentoEntrenamiento.objects.create(
            nombre=data['nombre'],
            lengua=lengua,
            modelo_base=modelo_audio,
            comunidades_usadas=data['comunidades'],
            config_entrenamiento=data.get('config', {}),
            estado=ExperimentoEntrenamiento.ESTADO_PENDIENTE,
        )

        # Lanzar entrenamiento asíncrono
        task_id = training_service.launch_training(
            experimento_id=str(exp.id),
            samples=samples,
            config=data.get('config', {}),
        )
        exp.task_id = task_id
        exp.save(update_fields=['task_id'])

        return Response(
            {
                'mensaje': 'Entrenamiento iniciado.',
                'experimento_id': str(exp.id),
                'task_id': task_id,
                'num_muestras': len(samples),
                'estado_url': f'/api/entrenamiento/experimentos/{exp.id}/estado/',
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ======================================================================
# Gestión de experimentos
# ======================================================================

class ExperimentoListView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Lista todos los experimentos de entrenamiento',
        responses={200: ExperimentoListSerializer(many=True)},
    )
    def get(self, request):
        lengua_id = request.query_params.get('lengua_id')
        estado = request.query_params.get('estado')

        qs = ExperimentoEntrenamiento.objects.select_related('lengua', 'modelo_base').all()
        if lengua_id:
            qs = qs.filter(lengua_id=lengua_id)
        if estado:
            qs = qs.filter(estado=estado)

        serializer = ExperimentoListSerializer(qs, many=True)
        return Response({'total': qs.count(), 'experimentos': serializer.data})


class ExperimentoDetailView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Detalle de un experimento (métricas, config, MLflow)',
        responses={
            200: ExperimentoDetailSerializer,
            404: OpenApiResponse(description='Experimento no encontrado'),
        },
    )
    def get(self, request, pk):
        try:
            exp = ExperimentoEntrenamiento.objects.select_related('lengua', 'modelo_base').get(pk=pk)
        except ExperimentoEntrenamiento.DoesNotExist:
            return Response({'error': 'Experimento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ExperimentoDetailSerializer(exp).data)


class ExperimentoEstadoView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Estado en tiempo real de un experimento',
        description='Útil para polling mientras el entrenamiento está en curso.',
        responses={
            200: OpenApiResponse(description='Estado actual del experimento'),
            404: OpenApiResponse(description='Experimento no encontrado'),
        },
    )
    def get(self, request, pk):
        try:
            exp = ExperimentoEntrenamiento.objects.select_related('lengua', 'modelo_base').get(pk=pk)
        except ExperimentoEntrenamiento.DoesNotExist:
            return Response({'error': 'Experimento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        task_info = training_service.get_task_info(exp.task_id) if exp.task_id else None

        return Response({
            'id': str(exp.id),
            'nombre': exp.nombre,
            'lengua': exp.lengua.codigo,
            'modelo': exp.modelo_base.nombre_hf,
            'estado': exp.estado,
            'is_active': exp.is_active,
            'num_muestras_train': exp.num_muestras_train,
            'num_muestras_eval': exp.num_muestras_eval,
            'metricas': exp.metricas,
            'mlflow_run_id': exp.mlflow_run_id,
            'mlflow_experiment_name': exp.mlflow_experiment_name,
            'task_info': task_info,
            'error_mensaje': exp.error_mensaje,
            'created_at': exp.created_at,
            'completed_at': exp.completed_at,
        })


class ExperimentoActivarView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Activar un modelo entrenado para su lengua',
        description=(
            'Marca este experimento como activo para la lengua correspondiente. '
            'El modelo será usado automáticamente por los endpoints de transcripción. '
            'Desactiva cualquier experimento activo anterior para la misma lengua.'
        ),
        responses={
            200: OpenApiResponse(description='Modelo activado exitosamente'),
            404: OpenApiResponse(description='Experimento no encontrado'),
            422: OpenApiResponse(description='El experimento no está completado'),
        },
    )
    def post(self, request, pk):
        try:
            exp = ExperimentoEntrenamiento.objects.select_related('lengua', 'modelo_base').get(pk=pk)
        except ExperimentoEntrenamiento.DoesNotExist:
            return Response({'error': 'Experimento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if exp.estado not in (
            ExperimentoEntrenamiento.ESTADO_COMPLETADO,
            ExperimentoEntrenamiento.ESTADO_ACTIVO,
        ):
            return Response(
                {
                    'error': (
                        f'No se puede activar un experimento con estado "{exp.estado}". '
                        'Debe estar en estado "completado" o "activo".'
                    )
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if not exp.ruta_modelo_entrenado or not Path(exp.ruta_modelo_entrenado).exists():
            return Response(
                {'error': 'La ruta del modelo entrenado no existe en disco.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        from django.db import transaction
        with transaction.atomic():
            # Desactivar experimento activo anterior de esta lengua
            ExperimentoEntrenamiento.objects.filter(
                lengua=exp.lengua,
                estado=ExperimentoEntrenamiento.ESTADO_ACTIVO,
            ).update(estado=ExperimentoEntrenamiento.ESTADO_COMPLETADO, is_active=False)

            exp.estado = ExperimentoEntrenamiento.ESTADO_ACTIVO
            exp.is_active = True
            exp.save(update_fields=['estado', 'is_active'])

        # Invalidar caché del modelo anterior si había uno
        model_service.invalidate_cache(exp.ruta_modelo_entrenado)

        logger.info(
            'Modelo ASR activado: lengua=%s experimento=%s', exp.lengua.codigo, exp.id
        )
        return Response({
            'mensaje': f'Modelo activado para lengua "{exp.lengua.nombre}".',
            'experimento_id': str(exp.id),
            'lengua': exp.lengua.codigo,
            'ruta_modelo': exp.ruta_modelo_entrenado,
            'mlflow_run_id': exp.mlflow_run_id,
        })


# ======================================================================
# Transcripción con el modelo activo
# ======================================================================

class TranscribirView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['Entrenamiento — Transcripción'],
        summary='Transcribir audio con el modelo ASR activo para una lengua',
        description=(
            'Recibe un archivo de audio y retorna la transcripción usando el modelo '
            'fine-tuneado y activado para la lengua indicada.'
        ),
        request=TranscribirRequestSerializer,
        responses={
            200: OpenApiResponse(description='Texto transcrito'),
            404: OpenApiResponse(description='Lengua no encontrada o sin modelo activo'),
            400: OpenApiResponse(description='Archivo de audio inválido'),
        },
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'lengua': 'iku',
                    'modelo': 'whisper-small-iku-v1',
                    'transcripcion': 'Du zari bunsi chano',
                    'ruta_audio_temporal': '/tmp/audio_xyz.wav',
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def post(self, request):
        serializer = TranscribirRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lengua_id = serializer.validated_data['lengua_id']
        audio_file = serializer.validated_data['audio']

        exp, error_resp = _get_active_experiment(lengua_id)
        if error_resp:
            return error_resp

        ext = Path(audio_file.name).suffix.lower()
        if ext not in AUDIO_EXTENSIONS_PERMITIDAS:
            return Response(
                {'error': f'Extensión "{ext}" no permitida. Usa: {", ".join(AUDIO_EXTENSIONS_PERMITIDAS)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            model, processor = model_service.load_asr_model(
                exp.ruta_modelo_entrenado, exp.modelo_base.tipo
            )
            transcripcion = model_service.transcribe_audio(
                tmp_path, model, processor, exp.modelo_base.tipo
            )
        except Exception as exc:
            logger.error('Error en transcripción: %s', exc, exc_info=True)
            return Response(
                {'error': f'Error al transcribir: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return Response({
            'lengua': exp.lengua.codigo,
            'modelo': exp.nombre,
            'transcripcion': transcripcion,
        })


class TranscribirTraducirView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['Entrenamiento — Transcripción'],
        summary='Transcribir audio y traducir el resultado (pipeline completo)',
        description=(
            'Pipeline completo audio → texto → traducción:\n\n'
            '1. El audio se transcribe con el modelo ASR fine-tuneado activo para la lengua.\n'
            '2. El texto transcrito entra al pipeline de traducción semántica '
            '(FAISS + embeddings).\n'
            '3. Se retornan la transcripción y los resultados de traducción.'
        ),
        request=TranscribirTraducirRequestSerializer,
        responses={
            200: OpenApiResponse(description='Transcripción + resultados de traducción'),
            404: OpenApiResponse(description='Lengua sin modelo ASR activo o sin embedding activo'),
            400: OpenApiResponse(description='Parámetros inválidos'),
        },
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'lengua': 'iku',
                    'modelo_asr': 'whisper-small-iku-v1',
                    'transcripcion': 'Du zari bunsi chano',
                    'traduccion': {
                        'direccion': 'iku→es',
                        'conclusion': {
                            'termino': 'Du zari bunsi chano',
                            'termino_es': 'buenos días',
                            'definicion': 'Saludo matutino en lengua ikʉn',
                            'probabilidad': 78.3,
                        },
                        'resultados': [],
                    },
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def post(self, request):
        serializer = TranscribirTraducirRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lengua_id = serializer.validated_data['lengua_id']
        audio_file = serializer.validated_data['audio']
        direccion = serializer.validated_data['direccion']
        top_k = serializer.validated_data['top_k']

        exp, error_resp = _get_active_experiment(lengua_id)
        if error_resp:
            return error_resp

        ext = Path(audio_file.name).suffix.lower()
        if ext not in AUDIO_EXTENSIONS_PERMITIDAS:
            return Response(
                {'error': f'Extensión "{ext}" no permitida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Transcripción ---
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            model, processor = model_service.load_asr_model(
                exp.ruta_modelo_entrenado, exp.modelo_base.tipo
            )
            transcripcion = model_service.transcribe_audio(
                tmp_path, model, processor, exp.modelo_base.tipo
            )
        except Exception as exc:
            logger.error('Error en transcripción: %s', exc, exc_info=True)
            return Response(
                {'error': f'Error al transcribir: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if not transcripcion:
            return Response(
                {'error': 'La transcripción resultó vacía. Verifica la calidad del audio.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # --- Traducción semántica ---
        traduccion_data = {}
        try:
            from terminos.models import EmbeddingVersion
            from traduccion.pipeline import TranslationPipeline
            from translator_api.search_engine import MultiLanguageSearchEngine

            embedding_activo = EmbeddingVersion.objects.filter(
                lengua=exp.lengua, status=EmbeddingVersion.STATUS_ACTIVE
            ).first()

            if embedding_activo is None:
                traduccion_data = {
                    'advertencia': (
                        f'La lengua "{exp.lengua.nombre}" no tiene embedding activo. '
                        'Genera y activa uno con /api/terminos/embeddings/.'
                    )
                }
            else:
                engine = MultiLanguageSearchEngine.get_instance()
                pipeline = TranslationPipeline(engine, language_code=exp.lengua.codigo)
                resultados = pipeline.translate(transcripcion, top_k=top_k)
                mejor = resultados[0] if resultados else None
                traduccion_data = {
                    'direccion': f'{exp.lengua.codigo}→es' if direccion == 'lengua_a_es' else f'es→{exp.lengua.codigo}',
                    'embedding_version': embedding_activo.version,
                    'conclusion': {
                        'termino': mejor['termino'],
                        'termino_es': mejor['termino_es'],
                        'definicion': mejor['definicion'],
                        'probabilidad': mejor['probabilidad'],
                    } if mejor else None,
                    'resultados': resultados,
                }
        except Exception as exc:
            logger.error('Error en traducción post-transcripción: %s', exc, exc_info=True)
            traduccion_data = {'error': f'Transcripción exitosa pero traducción falló: {exc}'}

        return Response({
            'lengua': exp.lengua.codigo,
            'modelo_asr': exp.nombre,
            'transcripcion': transcripcion,
            'traduccion': traduccion_data,
        })


# ======================================================================
# Helper
# ======================================================================

def _get_active_experiment(lengua_id: int):
    """Retorna (ExperimentoEntrenamiento activo, None) o (None, Response de error)."""
    try:
        from terminos.models import Lengua
        lengua = Lengua.objects.get(pk=lengua_id)
    except Lengua.DoesNotExist:
        return None, Response(
            {'error': f'Lengua id={lengua_id} no existe.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    exp = ExperimentoEntrenamiento.objects.filter(
        lengua=lengua,
        estado=ExperimentoEntrenamiento.ESTADO_ACTIVO,
        is_active=True,
    ).select_related('lengua', 'modelo_base').first()

    if exp is None:
        return None, Response(
            {
                'error': (
                    f'La lengua "{lengua.nombre}" no tiene un modelo ASR activo. '
                    'Entrena y activa un modelo con '
                    'POST /api/entrenamiento/entrenar/ y '
                    'POST /api/entrenamiento/experimentos/{id}/activar/'
                )
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if not exp.ruta_modelo_entrenado or not Path(exp.ruta_modelo_entrenado).exists():
        return None, Response(
            {'error': 'El modelo activo no se encuentra en disco. Reactiva otro experimento.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return exp, None
