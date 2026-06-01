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


class EntrenarRequestSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=255)
    lengua_id = serializers.IntegerField()
    modelo_audio_id = serializers.IntegerField()
    comunidades = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        help_text='Nombres de carpetas de comunidades a usar (ej: ["arhuaco", "kogui"])',
    )
    config = serializers.DictField(
        required=False,
        default=dict,
        help_text='Hiperparámetros opcionales (num_train_epochs, learning_rate, use_peft, etc.)',
    )


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
