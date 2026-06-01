import uuid

from django.db import models


class ModeloAudio(models.Model):
    """Modelo HuggingFace de reconocimiento de voz descargado localmente."""

    TIPO_WAV2VEC2 = 'wav2vec2'
    TIPO_WHISPER = 'whisper'
    TIPO_CHOICES = [
        (TIPO_WAV2VEC2, 'Wav2Vec2 (CTC)'),
        (TIPO_WHISPER, 'Whisper (Seq2Seq)'),
    ]

    nombre_hf = models.CharField(max_length=255, unique=True, db_index=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField(blank=True)
    ruta_local = models.CharField(max_length=500, blank=True)
    descargado = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modelos_audio'
        ordering = ['nombre_hf']
        verbose_name = 'Modelo de Audio'
        verbose_name_plural = 'Modelos de Audio'

    def __str__(self):
        return f"{self.nombre_hf} [{self.get_tipo_display()}]"


class ExperimentoEntrenamiento(models.Model):
    """
    Experimento de fine-tuning de un modelo ASR para una lengua indígena.

    Ciclo de vida:
      pendiente → entrenando → completado ←→ activo
                             └→ fallido
    """

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ENTRENANDO = 'entrenando'
    ESTADO_COMPLETADO = 'completado'
    ESTADO_ACTIVO = 'activo'
    ESTADO_FALLIDO = 'fallido'

    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ENTRENANDO, 'Entrenando'),
        (ESTADO_COMPLETADO, 'Completado'),
        (ESTADO_ACTIVO, 'Activo'),
        (ESTADO_FALLIDO, 'Fallido'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=255)

    lengua = models.ForeignKey(
        'terminos.Lengua',
        on_delete=models.CASCADE,
        related_name='experimentos_audio',
        db_index=True,
    )
    modelo_base = models.ForeignKey(
        ModeloAudio,
        on_delete=models.CASCADE,
        related_name='experimentos',
    )

    # Comunidades (carpetas de Grabaciones) usadas para construir el dataset
    comunidades_usadas = models.JSONField(default=list)

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_PENDIENTE,
        db_index=True,
    )
    is_active = models.BooleanField(default=False, db_index=True)

    # Hiperparámetros y config del entrenamiento
    config_entrenamiento = models.JSONField(default=dict)

    # Ruta al modelo fine-tuneado guardado en disco
    ruta_modelo_entrenado = models.CharField(max_length=500, blank=True)

    # MLflow
    mlflow_run_id = models.CharField(max_length=255, blank=True)
    mlflow_experiment_id = models.CharField(max_length=255, blank=True)
    mlflow_experiment_name = models.CharField(max_length=255, blank=True)
    mlflow_tracking_uri = models.CharField(max_length=500, blank=True)

    # Métricas finales (WER, CER, loss, etc.)
    metricas = models.JSONField(default=dict)

    # Número de muestras de entrenamiento/evaluación
    num_muestras_train = models.IntegerField(default=0)
    num_muestras_eval = models.IntegerField(default=0)

    error_mensaje = models.TextField(blank=True)
    task_id = models.CharField(max_length=255, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'experimentos_entrenamiento'
        ordering = ['-created_at']
        verbose_name = 'Experimento de Entrenamiento'
        verbose_name_plural = 'Experimentos de Entrenamiento'

    def __str__(self):
        return f"{self.nombre} [{self.lengua.codigo}] — {self.estado}"
