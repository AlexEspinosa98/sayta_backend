from rest_framework import serializers

from .models import ExperimentoEntrenamiento, ModeloAudio


class ModeloAudioSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = ModeloAudio
        fields = [
            'id', 'nombre_hf', 'tipo', 'tipo_display',
            'descripcion', 'ruta_local', 'descargado', 'created_at',
        ]
        read_only_fields = ['id', 'ruta_local', 'descargado', 'created_at']


class ExperimentoListSerializer(serializers.ModelSerializer):
    lengua_codigo = serializers.CharField(source='lengua.codigo', read_only=True)
    lengua_nombre = serializers.CharField(source='lengua.nombre', read_only=True)
    modelo_nombre = serializers.CharField(source='modelo_base.nombre_hf', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = ExperimentoEntrenamiento
        fields = [
            'id', 'nombre', 'lengua_codigo', 'lengua_nombre',
            'modelo_nombre', 'comunidades_usadas', 'estado', 'estado_display',
            'is_active', 'num_muestras_train', 'num_muestras_eval',
            'metricas', 'created_at', 'completed_at',
        ]


class ExperimentoDetailSerializer(serializers.ModelSerializer):
    lengua_codigo = serializers.CharField(source='lengua.codigo', read_only=True)
    lengua_nombre = serializers.CharField(source='lengua.nombre', read_only=True)
    modelo_base_info = ModeloAudioSerializer(source='modelo_base', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = ExperimentoEntrenamiento
        fields = [
            'id', 'nombre', 'lengua_codigo', 'lengua_nombre',
            'modelo_base_info', 'comunidades_usadas', 'estado', 'estado_display',
            'is_active', 'config_entrenamiento', 'ruta_modelo_entrenado',
            'mlflow_run_id', 'mlflow_experiment_id', 'mlflow_experiment_name',
            'mlflow_tracking_uri', 'metricas', 'num_muestras_train',
            'num_muestras_eval', 'error_mensaje', 'task_id',
            'created_at', 'completed_at',
        ]


# ── Data Augmentation ──────────────────────────────────────────────────────

class _TecnicaBaseSerializer(serializers.Serializer):
    habilitado = serializers.BooleanField(
        default=False,
        help_text='Activa esta técnica para el experimento.',
    )
    porcentaje = serializers.FloatField(
        min_value=1.0,
        max_value=100.0,
        required=False,
        help_text='Porcentaje de muestras de entrenamiento a las que se aplica esta técnica (1–100).',
    )


class RuidoGaussianoSerializer(_TecnicaBaseSerializer):
    intensidad = serializers.FloatField(
        min_value=0.001,
        max_value=0.05,
        required=False,
        help_text='Amplitud del ruido relativa a la señal. 0.005 = sutil, 0.03 = notable.',
    )


class CambioVelocidadSerializer(_TecnicaBaseSerializer):
    factor_min = serializers.FloatField(
        min_value=0.7,
        max_value=1.0,
        required=False,
        help_text='Factor mínimo de velocidad (0.9 = 10 %% más lento).',
    )
    factor_max = serializers.FloatField(
        min_value=1.0,
        max_value=1.3,
        required=False,
        help_text='Factor máximo de velocidad (1.1 = 10 %% más rápido).',
    )


class CambioTonoSerializer(_TecnicaBaseSerializer):
    semitonos_min = serializers.IntegerField(
        min_value=-6,
        max_value=0,
        required=False,
        help_text='Semitonos mínimos a desplazar (negativo = más grave). Ej: -2.',
    )
    semitonos_max = serializers.IntegerField(
        min_value=0,
        max_value=6,
        required=False,
        help_text='Semitonos máximos a desplazar (positivo = más agudo). Ej: 2.',
    )


class ReduccionVolumenSerializer(_TecnicaBaseSerializer):
    factor_min = serializers.FloatField(
        min_value=0.2,
        max_value=0.8,
        required=False,
        help_text='Factor mínimo de ganancia (0.5 = 50 %% del volumen original).',
    )
    factor_max = serializers.FloatField(
        min_value=0.6,
        max_value=1.0,
        required=False,
        help_text='Factor máximo de ganancia.',
    )


class RecorteTiempoSerializer(_TecnicaBaseSerializer):
    max_porcentaje_clip = serializers.IntegerField(
        min_value=5,
        max_value=30,
        required=False,
        help_text='Porcentaje máximo del audio a silenciar (10 = hasta el 10 %% de la duración).',
    )


class EcoSerializer(_TecnicaBaseSerializer):
    delay_ms = serializers.IntegerField(
        min_value=10,
        max_value=200,
        required=False,
        help_text='Retardo del eco en milisegundos. 30–80 ms = sala pequeña, 100–200 ms = espacio grande.',
    )
    decay = serializers.FloatField(
        min_value=0.05,
        max_value=0.5,
        required=False,
        help_text='Amplitud del eco relativa a la señal original (0.2 = 20 %%).',
    )


class TecnicasAugmentationSerializer(serializers.Serializer):
    ruido_gaussiano = RuidoGaussianoSerializer(
        required=False,
        help_text='Ruido blanco gaussiano. Simula grabaciones con ruido ambiental.',
    )
    cambio_velocidad = CambioVelocidadSerializer(
        required=False,
        help_text='Time stretching sin cambio de tono. Simula variaciones en velocidad del hablante.',
    )
    cambio_tono = CambioTonoSerializer(
        required=False,
        help_text='Pitch shifting sin cambio de velocidad. Simula diferentes tipos de hablantes.',
    )
    reduccion_volumen = ReduccionVolumenSerializer(
        required=False,
        help_text='Reducción aleatoria de ganancia. Simula micrófono a mayor distancia.',
    )
    recorte_tiempo = RecorteTiempoSerializer(
        required=False,
        help_text='Enmascaramiento temporal (Time Masking). Regularización inspirada en SpecAugment.',
    )
    eco = EcoSerializer(
        required=False,
        help_text='Eco simple. Simula grabaciones en espacios con reverberación (maloca, aula).',
    )


class AugmentationSerializer(serializers.Serializer):
    habilitado = serializers.BooleanField(
        default=False,
        help_text='Activa o desactiva el data augmentation para este experimento.',
    )
    tecnicas = TecnicasAugmentationSerializer(
        required=False,
        help_text=(
            'Configuración de cada técnica. '
            'Solo se aplican las que tengan `habilitado: true`. '
            'Consulta GET /api/entrenamiento/dataset/augmentation/ para ver el catálogo completo.'
        ),
    )


class SesionSerializer(serializers.Serializer):
    """Par (comunidad, jornada) para selección granular de datos."""
    comunidad = serializers.CharField(
        help_text='Nombre de la carpeta de comunidad (ej: "arhuaco")',
    )
    jornada = serializers.CharField(
        help_text='Nombre de la sub-carpeta de jornada (ej: "grabacion_15_03_26_fauna")',
    )


class EntrenarRequestSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=255)
    lengua_id = serializers.IntegerField(
        help_text='ID de la Lengua en la base de datos (ver GET /api/entrenamiento/lenguas/)',
    )
    modelo_audio_id = serializers.IntegerField(
        help_text='ID del ModeloAudio descargado (ver GET /api/entrenamiento/modelos/)',
    )

    # ── Selección de dataset — exactamente uno de estos tres debe estar presente ──
    todos = serializers.BooleanField(
        required=False,
        default=False,
        help_text='Si true, usa TODOS los audios etiquetados sin importar comunidad o jornada.',
    )
    sesiones = serializers.ListField(
        child=SesionSerializer(),
        required=False,
        default=list,
        help_text=(
            'Jornadas específicas a incluir.\n'
            'Ej: [{"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"}]'
        ),
    )
    comunidades = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text='Comunidades completas (todas sus jornadas). Ej: ["arhuaco", "kogui"]',
    )

    config = serializers.DictField(
        required=False,
        default=dict,
        help_text=(
            'Hiperparámetros opcionales:\n'
            '  num_train_epochs (int, default 20)\n'
            '  learning_rate (float)\n'
            '  per_device_train_batch_size (int, default 1 whisper / 4 wav2vec2)\n'
            '  gradient_accumulation_steps (int, default 8 whisper / 2 wav2vec2)\n'
            '  warmup_steps (int, default 100)\n'
            '  use_peft (bool, default false)\n'
            '  peft_r (int, default 16)\n'
            '  whisper_language (str, default "es")'
        ),
    )
    augmentation = AugmentationSerializer(
        required=False,
        help_text=(
            'Configuración de Data Augmentation. '
            'Genera muestras adicionales a partir del dataset original para mejorar '
            'la robustez del modelo. '
            'Consulta GET /api/entrenamiento/dataset/augmentation/ para el catálogo de técnicas.'
        ),
    )

    def validate(self, data):
        todos = data.get('todos', False)
        sesiones = data.get('sesiones', [])
        comunidades = data.get('comunidades', [])

        if not todos and not sesiones and not comunidades:
            raise serializers.ValidationError(
                'Debes especificar al menos uno: '
                '"todos": true, "sesiones": [...], o "comunidades": [...]'
            )
        return data


class SubirAudioSerializer(serializers.Serializer):
    comunidad = serializers.CharField(
        max_length=100,
        help_text='Nombre de la comunidad (ej: "arhuaco", "kogui"). Se crea si no existe.',
    )
    jornada = serializers.CharField(
        max_length=100,
        help_text='Nombre de la jornada o sesión (ej: "grabacion_junio_2026"). Se crea si no existe.',
    )
    audio = serializers.FileField(
        help_text='Archivo de audio (.wav, .mp3, .ogg, .flac, .m4a, .mp4)',
    )
    transcripcion = serializers.CharField(
        allow_blank=False,
        help_text='Texto transcrito del audio en la lengua indígena correspondiente.',
    )

    def validate_audio(self, value):
        from pathlib import Path
        PERMITIDAS = {'.wav', '.mp3', '.mp4', '.m4a', '.ogg', '.flac'}
        ext = Path(value.name).suffix.lower()
        if ext not in PERMITIDAS:
            raise serializers.ValidationError(
                f'Extensión "{ext}" no permitida. Usa: {", ".join(sorted(PERMITIDAS))}'
            )
        return value

    def validate_comunidad(self, value):
        import re
        limpio = re.sub(r'[^\w\-]', '_', value.strip().lower())
        if not limpio:
            raise serializers.ValidationError('Nombre de comunidad inválido.')
        return limpio

    def validate_jornada(self, value):
        import re
        limpio = re.sub(r'[^\w\-]', '_', value.strip().lower())
        if not limpio:
            raise serializers.ValidationError('Nombre de jornada inválido.')
        return limpio


class TranscribirRequestSerializer(serializers.Serializer):
    lengua_id = serializers.IntegerField()
    audio = serializers.FileField(
        help_text='Archivo de audio (.wav, .mp3, .ogg, .flac, .m4a)',
    )


class TranscribirTraducirRequestSerializer(serializers.Serializer):
    lengua_id = serializers.IntegerField()
    audio = serializers.FileField()
    direccion = serializers.ChoiceField(
        choices=['es_a_lengua', 'lengua_a_es'],
        default='lengua_a_es',
        help_text='Dirección de traducción del texto transcrito',
    )
    top_k = serializers.IntegerField(default=3, min_value=1, max_value=10)
