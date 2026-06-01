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
            '  per_device_train_batch_size (int, default 4)\n'
            '  gradient_accumulation_steps (int, default 2)\n'
            '  warmup_steps (int, default 100)\n'
            '  use_peft (bool, default false)\n'
            '  peft_r (int, default 16)\n'
            '  whisper_language (str, default "es")'
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
