"""
Módulo de entrenamiento de modelos ASR para lenguas indígenas.

Endpoints:
  GET  /api/entrenamiento/sistema/                         Recursos del servidor (CPU, GPU, RAM)
  POST /api/entrenamiento/sistema/liberar-memoria/          Libera modelos cacheados y caché CUDA
  GET  /api/entrenamiento/modelos-disponibles/             Catálogo curado de modelos HF
  GET  /api/entrenamiento/modelos/                         Modelos descargados
  POST /api/entrenamiento/modelos/descargar/               Descarga un modelo desde HF Hub
  GET  /api/entrenamiento/dataset/                         Stats de datos etiquetados por comunidad
  GET  /api/entrenamiento/dataset/estadisticas/            Tiempo de grabación y cantidad de archivos por comunidad
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

from usuarios.permissions import EsAnotador, EsInvestigador
from .models import ExperimentoEntrenamiento, ModeloAudio
from .serializers import (
    EntrenarRequestSerializer,
    ExperimentoDetailSerializer,
    ExperimentoListSerializer,
    ModeloAudioSerializer,
    SubirAudioSerializer,
    TranscribirRequestSerializer,
    TranscribirTraducirRequestSerializer,
    SesionSerializer,
)
from .services import augmentation_service, dataset_service, model_service, training_service

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
    permission_classes = [EsInvestigador]

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


class SubirAudioView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [EsAnotador]

    @extend_schema(
        tags=['Entrenamiento — Dataset'],
        summary='Subir un audio con su transcripción al dataset de entrenamiento',
        description=(
            'Guarda un archivo de audio y su transcripción en la estructura de Grabaciones '
            'del servidor, organizándolo por comunidad y jornada.\n\n'
            '**Estructura resultante en disco:**\n'
            '```\n'
            'Grabaciones/\n'
            '  <comunidad>/\n'
            '    <jornada>/\n'
            '      audios_sin_procesar/  ← audio guardado aquí\n'
            '      audios_procesados/    ← transcripción .txt guardada aquí\n'
            '```\n\n'
            'La comunidad y jornada se crean automáticamente si no existen. '
            'Si el nombre de archivo ya existe, se añade un sufijo de timestamp.\n\n'
            '**Formatos de audio aceptados:** .wav, .mp3, .mp4, .m4a, .ogg, .flac'
        ),
        request=SubirAudioSerializer,
        responses={
            201: OpenApiResponse(description='Audio guardado exitosamente'),
            400: OpenApiResponse(description='Parámetros inválidos o extensión no permitida'),
            500: OpenApiResponse(description='Error al guardar en disco'),
        },
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'mensaje': 'Audio guardado exitosamente.',
                    'comunidad': 'arhuaco',
                    'jornada': 'grabacion_junio_2026',
                    'archivo_audio': 'saludo_001.wav',
                    'duracion_segundos': 8.4,
                    'transcripcion_guardada': 'Nakua se wintukua',
                    'ruta_relativa': 'Grabaciones/arhuaco/grabacion_junio_2026/audios_sin_procesar/saludo_001.wav',
                    'jornada_stats': {
                        'total_audios': 15,
                        'etiquetados': 15,
                        'sin_etiquetar': 0,
                        'porcentaje': 100.0,
                    },
                },
                response_only=True,
                status_codes=['201'],
            ),
        ],
    )
    def post(self, request):
        serializer = SubirAudioSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            resultado = dataset_service.save_audio_sample(
                comunidad=data['comunidad'],
                jornada=data['jornada'],
                audio_file=data['audio'],
                transcripcion=data['transcripcion'],
            )
        except Exception as exc:
            logger.error('Error guardando audio: %s', exc, exc_info=True)
            return Response(
                {'error': f'Error al guardar el audio en disco: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {'mensaje': 'Audio guardado exitosamente.', **resultado},
            status=status.HTTP_201_CREATED,
        )


class AugmentationCatalogoView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Dataset'],
        summary='Catálogo de técnicas de Data Augmentation disponibles',
        description=(
            'Devuelve todas las técnicas de aumento de datos disponibles con sus parámetros, '
            'rangos, valores por defecto y un ejemplo de configuración listo para copiar '
            'en el campo `augmentation` de `POST /api/entrenamiento/entrenar/`.\n\n'
            '**¿Qué es Data Augmentation?**\n'
            'Genera nuevas muestras de entrenamiento a partir de las existentes aplicando '
            'transformaciones de audio (ruido, velocidad, tono, etc.), sin modificar los '
            'archivos originales. Cada muestra aumentada hereda la transcripción del original.\n\n'
            '**¿Cuándo usarlo?**\n'
            'Especialmente útil cuando el dataset es pequeño (< 500 muestras). '
            'Con un 30 % de ruido gaussiano sobre 100 muestras se obtienen 30 muestras extra, '
            'totalizando 130 muestras de entrenamiento.\n\n'
            '**Nota metodológica:** el augmentation se aplica ANTES del split train/eval, '
            'por lo que el conjunto de evaluación puede contener muestras aumentadas. '
            'Para un control más estricto, usa K-Fold (`use_cv: true`), donde la augmentation '
            'se aplica por fold solo al split de entrenamiento.'
        ),
        responses={200: OpenApiResponse(description='Catálogo de técnicas con parámetros y ejemplos')},
        examples=[
            OpenApiExample(
                'Respuesta parcial',
                value={
                    'total_tecnicas': 6,
                    'tecnicas': {
                        'ruido_gaussiano': {
                            'nombre': 'Ruido Gaussiano',
                            'recomendado': True,
                            'porcentaje_default': 30,
                            'impacto_tiempo': 'bajo',
                            'config_ejemplo': {
                                'habilitado': True,
                                'porcentaje': 30,
                                'intensidad': 0.005,
                            },
                        },
                        'cambio_velocidad': {
                            'nombre': 'Cambio de Velocidad (Time Stretching)',
                            'recomendado': True,
                            'porcentaje_default': 20,
                            'impacto_tiempo': 'medio',
                            'config_ejemplo': {
                                'habilitado': True,
                                'porcentaje': 20,
                                'factor_min': 0.9,
                                'factor_max': 1.1,
                            },
                        },
                    },
                    'ejemplo_completo_para_entrenar': {
                        'habilitado': True,
                        'tecnicas': {
                            'ruido_gaussiano': {'habilitado': True, 'porcentaje': 30, 'intensidad': 0.005},
                            'cambio_velocidad': {'habilitado': True, 'porcentaje': 20},
                            'cambio_tono': {'habilitado': True, 'porcentaje': 20},
                            'reduccion_volumen': {'habilitado': False},
                            'recorte_tiempo': {'habilitado': False},
                            'eco': {'habilitado': False},
                        },
                    },
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def get(self, request):
        catalogo = augmentation_service.get_catalogo_completo()
        tecnicas_recomendadas = [k for k, v in catalogo.items() if v.get('recomendado')]

        ejemplo_completo = {
            'habilitado': True,
            'tecnicas': {
                nombre: info['config_ejemplo']
                for nombre, info in catalogo.items()
            },
        }

        return Response({
            'total_tecnicas': len(catalogo),
            'tecnicas_recomendadas': tecnicas_recomendadas,
            'tecnicas': catalogo,
            'ejemplo_completo_para_entrenar': ejemplo_completo,
        })


class EstadisticasGrabacionesView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Dataset'],
        summary='Estadísticas de tiempo de grabación por comunidad',
        description=(
            'Escanea todos los archivos de audio en disco y calcula el tiempo total '
            'de grabación y la cantidad de archivos, desglosados por comunidad y jornada.\n\n'
            'La duración se extrae de los metadatos del audio (no se decodifica el contenido). '
            'Si un archivo no puede ser leído, se cuenta en `archivos_sin_duracion`.'
        ),
        responses={200: OpenApiResponse(description='Estadísticas de tiempo de grabación')},
        examples=[
            OpenApiExample(
                'Respuesta exitosa',
                value={
                    'base_path': '/mnt/sayta_data/data/Grabaciones',
                    'existe': True,
                    'resumen_global': {
                        'total_comunidades': 2,
                        'total_archivos': 150,
                        'duracion_segundos': 3600.0,
                        'duracion_formateada': '1h 00m 00s',
                        'archivos_sin_duracion': 0,
                    },
                    'por_comunidad': [
                        {
                            'comunidad': 'arhuaco',
                            'total_archivos': 90,
                            'duracion_segundos': 2160.0,
                            'duracion_formateada': '36m 00s',
                            'archivos_sin_duracion': 0,
                            'jornadas': [
                                {
                                    'jornada': 'grabacion_junio_2026',
                                    'total_archivos': 30,
                                    'duracion_segundos': 720.0,
                                    'duracion_formateada': '12m 00s',
                                    'archivos_sin_duracion': 0,
                                }
                            ],
                        }
                    ],
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    def get(self, request):
        stats = dataset_service.get_recording_time_stats()
        return Response(stats)


class DatasetSesionesView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Dataset'],
        summary='Lista plana de todas las jornadas disponibles (para selección granular)',
        description=(
            'Retorna TODAS las jornadas de TODAS las comunidades con sus conteos de audios '
            'etiquetados. El frontend puede mostrar checkboxes individuales por jornada.\n\n'
            'Usar `apta: true` para filtrar las que tienen al menos un audio etiquetado.'
        ),
        responses={200: OpenApiResponse(description='Lista plana de jornadas con estadísticas')},
    )
    def get(self, request):
        data = dataset_service.get_all_sessions()
        return Response(data)


# ======================================================================
# Lenguas con información de estado ASR
# ======================================================================

class LenguasEntrenamientoView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Lenguas'],
        summary='Lista de lenguas activas con estado de modelos ASR',
        description=(
            'Retorna las lenguas registradas en la base de datos con información '
            'de si tienen un modelo ASR activo, cuántos modelos están descargados, '
            'y el detalle del experimento activo (si existe).\n\n'
            'Usar el `id` de esta respuesta como `lengua_id` en el endpoint de entrenamiento.'
        ),
        responses={200: OpenApiResponse(description='Lenguas activas con estado ASR')},
    )
    def get(self, request):
        from terminos.models import Lengua

        lenguas = Lengua.objects.filter(activa=True).order_by('nombre')
        modelos_desc = ModeloAudio.objects.filter(descargado=True)

        result = []
        for lengua in lenguas:
            exp_activo = (
                ExperimentoEntrenamiento.objects
                .filter(lengua=lengua, is_active=True)
                .select_related('modelo_base')
                .first()
            )
            ultimo_exp = (
                ExperimentoEntrenamiento.objects
                .filter(lengua=lengua)
                .order_by('-created_at')
                .select_related('modelo_base')
                .first()
            )
            result.append({
                'id': lengua.id,
                'codigo': lengua.codigo,
                'nombre': lengua.nombre,
                'tiene_modelo_activo': exp_activo is not None,
                'modelo_activo': {
                    'experimento_id': str(exp_activo.id),
                    'nombre': exp_activo.nombre,
                    'modelo_hf': exp_activo.modelo_base.nombre_hf,
                    'metricas': exp_activo.metricas,
                    'completed_at': exp_activo.completed_at,
                } if exp_activo else None,
                'ultimo_experimento': {
                    'id': str(ultimo_exp.id),
                    'nombre': ultimo_exp.nombre,
                    'estado': ultimo_exp.estado,
                    'created_at': ultimo_exp.created_at,
                } if ultimo_exp and not exp_activo else None,
                'modelos_descargados': modelos_desc.count(),
                'modelos_disponibles_para_entrenar': [
                    {'id': m.id, 'nombre_hf': m.nombre_hf, 'tipo': m.tipo}
                    for m in modelos_desc
                ],
            })

        return Response({'total': len(result), 'lenguas': result})


# ======================================================================
# Entrenamiento
# ======================================================================

class EntrenarView(APIView):
    permission_classes = [EsInvestigador]

    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Lanzar fine-tuning de un modelo ASR (asíncrono)',
        description=(
            'Dispara el entrenamiento en segundo plano. Retorna inmediatamente con el '
            '`id` del experimento. Monitorea el estado con '
            '`GET /api/entrenamiento/experimentos/{id}/estado/`.\n\n'
            '**Obtener IDs necesarios:**\n'
            '- `lengua_id` → `GET /api/entrenamiento/lenguas/`\n'
            '- `modelo_audio_id` → `GET /api/entrenamiento/modelos/`\n\n'
            '**Modos de selección de datos (elige uno):**\n'
            '- `"todos": true` — usa TODOS los audios etiquetados del sistema\n'
            '- `"sesiones": [{comunidad, jornada}, ...]` — jornadas específicas (granular)\n'
            '- `"comunidades": ["arhuaco", ...]` — comunidades completas\n\n'
            'Ver jornadas disponibles en `GET /api/entrenamiento/dataset/sesiones/`.\n\n'
            '**Config opcionales:**\n'
            '- `num_train_epochs` (int, default 20)\n'
            '- `learning_rate` (float, default 1e-4 para wav2vec2 / 1e-5 para whisper)\n'
            '- `per_device_train_batch_size` (int, default 1 para whisper / 4 para wav2vec2)\n'
            '- `gradient_accumulation_steps` (int, default 8 para whisper / 2 para wav2vec2)\n'
            '- `warmup_steps` (int, default 100)\n'
            '- `use_peft` (bool, default false) — LoRA para fine-tuning eficiente\n'
            '- `peft_r` (int, default 16)\n'
            '- `whisper_language` (str, default "es")\n'
        ),
        request=EntrenarRequestSerializer,
        responses={
            202: OpenApiResponse(description='Entrenamiento iniciado (asíncrono)'),
            400: OpenApiResponse(description='Parámetros inválidos'),
            404: OpenApiResponse(description='Lengua o modelo no encontrados'),
            409: OpenApiResponse(description='Ya hay un entrenamiento en curso'),
            422: OpenApiResponse(description='Datos insuficientes para entrenar'),
        },
        examples=[
            OpenApiExample(
                'Modo: todos los audios',
                value={
                    'nombre': 'whisper-small-iku-v1-full',
                    'lengua_id': 1,
                    'modelo_audio_id': 1,
                    'todos': True,
                    'config': {'num_train_epochs': 20, 'use_peft': False},
                },
                request_only=True,
            ),
            OpenApiExample(
                'Modo: jornadas específicas',
                value={
                    'nombre': 'whisper-small-iku-fauna',
                    'lengua_id': 1,
                    'modelo_audio_id': 1,
                    'sesiones': [
                        {'comunidad': 'arhuaco', 'jornada': 'grabacion_15_03_26_fauna'},
                        {'comunidad': 'arhuaco', 'jornada': 'grabacion_20_04_26_animales'},
                    ],
                    'config': {'num_train_epochs': 15},
                },
                request_only=True,
            ),
            OpenApiExample(
                'Modo: comunidades completas',
                value={
                    'nombre': 'whisper-small-bilingue-v1',
                    'lengua_id': 1,
                    'modelo_audio_id': 1,
                    'comunidades': ['arhuaco', 'kogui'],
                    'config': {'num_train_epochs': 20, 'use_peft': True, 'peft_r': 16},
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

        raw_config = dict(data.get('config') or {})
        aug_data = data.get('augmentation')
        if aug_data:
            raw_config['augmentation'] = aug_data
        config, config_warnings = _normalize_training_config(modelo_audio, raw_config)

        # Verificar que no haya otro entrenamiento activo compitiendo por GPU/RAM
        entrenando = ExperimentoEntrenamiento.objects.filter(
            estado=ExperimentoEntrenamiento.ESTADO_ENTRENANDO,
        ).select_related('lengua', 'modelo_base').first()
        if entrenando:
            return Response(
                {
                    'error': 'Ya hay un entrenamiento en curso. Espera a que termine o cancélalo antes de iniciar otro.',
                    'experimento_id': str(entrenando.id),
                    'nombre': entrenando.nombre,
                    'lengua': entrenando.lengua.codigo,
                    'modelo': entrenando.modelo_base.nombre_hf,
                    'estado_url': f'/api/entrenamiento/experimentos/{entrenando.id}/estado/',
                },
                status=status.HTTP_409_CONFLICT,
            )

        # ── Construir dataset según modo de selección ──────────────────
        todos = data.get('todos', False)
        sesiones = data.get('sesiones', [])
        comunidades_sel = data.get('comunidades', [])

        if todos:
            samples = dataset_service.build_all_samples()
            seleccion_info = {'modo': 'todos'}
        elif sesiones:
            samples = dataset_service.build_samples_from_sessions(sesiones)
            seleccion_info = {'modo': 'sesiones', 'sesiones': sesiones}
        else:
            samples = dataset_service.build_samples_from_communities(comunidades_sel)
            seleccion_info = {'modo': 'comunidades', 'comunidades': comunidades_sel}

        if len(samples) < dataset_service.MIN_MUESTRAS_ENTRENAMIENTO:
            return Response(
                {
                    'error': (
                        f'Se necesitan al menos {dataset_service.MIN_MUESTRAS_ENTRENAMIENTO} '
                        f'muestras etiquetadas. Solo se encontraron {len(samples)}. '
                        'Etiqueta más audios antes de entrenar.'
                    ),
                    'muestras_encontradas': len(samples),
                    'seleccion': seleccion_info,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Crear experimento en BD
        exp = ExperimentoEntrenamiento.objects.create(
            nombre=data['nombre'],
            lengua=lengua,
            modelo_base=modelo_audio,
            comunidades_usadas=seleccion_info,
            config_entrenamiento=config,
            estado=ExperimentoEntrenamiento.ESTADO_PENDIENTE,
        )

        # Lanzar entrenamiento asíncrono
        task_id = training_service.launch_training(
            experimento_id=str(exp.id),
            samples=samples,
            config=config,
        )
        exp.task_id = task_id
        exp.save(update_fields=['task_id'])

        return Response(
            {
                'mensaje': 'Entrenamiento iniciado.',
                'experimento_id': str(exp.id),
                'task_id': task_id,
                'num_muestras': len(samples),
                'config_usada': config,
                'advertencias_config': config_warnings,
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


class ExperimentoCancelarView(APIView):
    permission_classes = [EsInvestigador]

    @extend_schema(
        tags=['Entrenamiento — Experimentos'],
        summary='Cancelar un entrenamiento en curso',
        description=(
            'Envía una señal de parada al hilo de entrenamiento. '
            'El proceso termina limpiamente al final del paso actual (puede tardar '
            'hasta ~30 segundos en procesarse). '
            'El experimento quedará en estado `fallido` con mensaje "Cancelado manualmente".'
        ),
        responses={
            200: OpenApiResponse(description='Señal de cancelación enviada'),
            404: OpenApiResponse(description='Experimento no encontrado'),
            409: OpenApiResponse(description='El experimento no está en curso'),
        },
    )
    def post(self, request, pk):
        try:
            exp = ExperimentoEntrenamiento.objects.get(pk=pk)
        except ExperimentoEntrenamiento.DoesNotExist:
            return Response({'error': 'Experimento no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        if exp.estado != ExperimentoEntrenamiento.ESTADO_ENTRENANDO:
            return Response(
                {'error': f'El experimento tiene estado "{exp.estado}", no está en curso.'},
                status=status.HTTP_409_CONFLICT,
            )

        cancelado = training_service.request_cancellation(exp.task_id) if exp.task_id else False

        if not cancelado:
            # El hilo ya murió pero la BD no se actualizó — resetear manualmente
            from django.utils import timezone
            exp.estado = ExperimentoEntrenamiento.ESTADO_FALLIDO
            exp.error_mensaje = 'Cancelado manualmente (hilo ya no activo)'
            exp.completed_at = timezone.now()
            exp.save(update_fields=['estado', 'error_mensaje', 'completed_at'])
            return Response({
                'mensaje': 'Hilo no encontrado — experimento marcado como fallido directamente.',
                'experimento_id': str(exp.id),
                'estado': exp.estado,
            })

        return Response({
            'mensaje': 'Señal de cancelación enviada. El entrenamiento parará al final del paso actual.',
            'experimento_id': str(exp.id),
            'estado_url': f'/api/entrenamiento/experimentos/{exp.id}/estado/',
        })


class ExperimentoActivarView(APIView):
    permission_classes = [EsInvestigador]

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
# Estado del sistema (CPU / GPU / RAM)
# ======================================================================

class SistemaView(APIView):
    @extend_schema(
        tags=['Entrenamiento — Sistema'],
        summary='Recursos del servidor disponibles para entrenamiento',
        description=(
            'Devuelve información sobre CPU, RAM y GPU del servidor. '
            'Útil para diagnosticar por qué el entrenamiento es lento '
            '(sin GPU el fine-tuning puede tardar 10-20× más).\n\n'
            '**`gpu_disponible: false`** → el contenedor no tiene acceso a GPU. '
            'Configura `deploy.resources.reservations.devices` en docker-compose.yml '
            'y asegúrate de tener NVIDIA Container Toolkit instalado en el host.'
        ),
        responses={200: OpenApiResponse(description='Información de recursos del servidor')},
    )
    def get(self, request):
        import platform
        import torch

        # ── GPU ──────────────────────────────────────────────────────────────
        gpu_info = []
        gpu_disponible = torch.cuda.is_available()
        if gpu_disponible:
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                mem_total = props.total_memory / 1024 ** 3
                mem_reservada = torch.cuda.memory_reserved(i) / 1024 ** 3
                mem_asignada = torch.cuda.memory_allocated(i) / 1024 ** 3
                gpu_info.append({
                    'indice': i,
                    'nombre': props.name,
                    'memoria_total_gb': round(mem_total, 2),
                    'memoria_reservada_gb': round(mem_reservada, 2),
                    'memoria_asignada_gb': round(mem_asignada, 2),
                    'memoria_libre_gb': round(mem_total - mem_reservada, 2),
                    'cuda_capability': f'{props.major}.{props.minor}',
                    'multiprocessors': props.multi_processor_count,
                })

        # ── CPU ──────────────────────────────────────────────────────────────
        cpu_info: dict = {'nucleos_logicos': os.cpu_count() or 0}
        try:
            import psutil
            cpu_info['uso_porcentaje'] = psutil.cpu_percent(interval=0.5)
            cpu_info['nucleos_fisicos'] = psutil.cpu_count(logical=False)
        except ImportError:
            pass

        # Intentar leer /proc/cpuinfo en Linux
        try:
            with open('/proc/cpuinfo', 'r') as f:
                lines = f.readlines()
            modelos = {l.split(':')[1].strip() for l in lines if l.startswith('model name')}
            if modelos:
                cpu_info['modelo'] = list(modelos)[0]
        except OSError:
            cpu_info['modelo'] = platform.processor() or 'desconocido'

        # ── RAM ───────────────────────────────────────────────────────────────
        ram_info: dict = {}
        try:
            import psutil
            vm = psutil.virtual_memory()
            ram_info = {
                'total_gb': round(vm.total / 1024 ** 3, 2),
                'disponible_gb': round(vm.available / 1024 ** 3, 2),
                'usado_gb': round(vm.used / 1024 ** 3, 2),
                'uso_porcentaje': vm.percent,
            }
        except ImportError:
            try:
                mem = {}
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        key, val = line.split(':')
                        mem[key.strip()] = int(val.strip().split()[0])
                ram_info = {
                    'total_gb': round(mem.get('MemTotal', 0) / 1024 ** 2, 2),
                    'disponible_gb': round(mem.get('MemAvailable', 0) / 1024 ** 2, 2),
                    'usado_gb': round((mem.get('MemTotal', 0) - mem.get('MemAvailable', 0)) / 1024 ** 2, 2),
                }
            except OSError:
                ram_info = {'error': 'No se pudo leer /proc/meminfo'}

        # ── Entrenamiento activo ──────────────────────────────────────────────
        entrenando = ExperimentoEntrenamiento.objects.filter(
            estado=ExperimentoEntrenamiento.ESTADO_ENTRENANDO
        ).select_related('lengua', 'modelo_base').first()

        entrenamiento_activo = None
        if entrenando:
            task_info = training_service.get_task_info(entrenando.task_id) if entrenando.task_id else None
            entrenamiento_activo = {
                'experimento_id': str(entrenando.id),
                'nombre': entrenando.nombre,
                'lengua': entrenando.lengua.codigo,
                'modelo': entrenando.modelo_base.nombre_hf,
                'started_at': task_info.get('started_at') if task_info else None,
                'estado_hilo': task_info.get('estado') if task_info else 'desconocido (hilo no activo)',
                'usando_gpu': gpu_disponible,
                'fp16_activado': gpu_disponible,
            }

        # ── Recomendaciones ───────────────────────────────────────────────────
        advertencias = []
        if not gpu_disponible:
            advertencias.append(
                'GPU no disponible: el entrenamiento corre en CPU y puede tardar 10-20× más. '
                'Añade soporte GPU al contenedor Docker con NVIDIA Container Toolkit.'
            )
        if ram_info.get('disponible_gb', 999) < 4:
            advertencias.append(
                f'RAM disponible baja ({ram_info.get("disponible_gb")} GB). '
                'Riesgo de OOM durante carga de modelo o chunking de audios.'
            )

        return Response({
            'gpu': {
                'disponible': gpu_disponible,
                'torch_version': torch.__version__,
                'cuda_version': torch.version.cuda if gpu_disponible else None,
                'dispositivos': gpu_info,
            },
            'cpu': cpu_info,
            'ram': ram_info,
            'sistema_operativo': platform.system(),
            'entrenamiento_en_curso': entrenamiento_activo,
            'advertencias': advertencias,
        })


class SistemaLiberarMemoriaView(APIView):
    permission_classes = [EsInvestigador]

    @extend_schema(
        tags=['Entrenamiento — Sistema'],
        summary='Liberar modelos cacheados y caché CUDA del servidor',
        description=(
            'Descarga de memoria los modelos ASR cacheados para transcripción y '
            'vacía la caché CUDA retenida por PyTorch en este proceso. Úsalo antes '
            'de lanzar entrenamiento si hubo transcripciones o entrenamientos previos.'
        ),
        responses={200: OpenApiResponse(description='Memoria liberada')},
    )
    def post(self, request):
        cache_before = model_service.cache_info()
        released_models = model_service.clear_model_cache()
        torch_cleanup = training_service.cleanup_torch_memory()

        return Response({
            'mensaje': 'Memoria de modelos liberada.',
            'modelos_cacheados_liberados': released_models,
            'cache_antes': cache_before,
            'cache_despues': model_service.cache_info(),
            'torch': torch_cleanup,
        })


# ======================================================================
# Helper
# ======================================================================

def _normalize_training_config(modelo_audio: ModeloAudio, config: dict) -> tuple[dict, list[str]]:
    normalized = dict(config or {})
    warnings = []

    if modelo_audio.tipo != ModeloAudio.TIPO_WHISPER:
        return normalized, warnings

    model_name = modelo_audio.nombre_hf.lower()
    is_memory_sensitive = 'whisper-small' in model_name or 'whisper-medium' in model_name
    if not is_memory_sensitive:
        return normalized, warnings

    if normalized.get('allow_full_finetune', False):
        warnings.append(
            'allow_full_finetune=true: se conserva la configuración solicitada, '
            'pero Whisper Small/Medium puede fallar en GPU de 8 GB.'
        )
        return normalized, warnings

    desired = {
        'per_device_train_batch_size': 1,
        'per_device_eval_batch_size': 1,
        'gradient_accumulation_steps': max(int(normalized.get('gradient_accumulation_steps', 8)), 8),
        'gradient_checkpointing': True,
        'fp16': True,
        'use_peft': True,
        'peft_r': int(normalized.get('peft_r', 8)),
        'peft_alpha': int(normalized.get('peft_alpha', 16)),
        'clear_asr_cache_before_training': True,
    }

    for key, value in desired.items():
        previous = normalized.get(key)
        if previous != value:
            normalized[key] = value
            warnings.append(f'{key} ajustado de {previous!r} a {value!r} para evitar OOM/NCCL en GPU de 8 GB.')

    return normalized, warnings


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
