import uuid

from django.db import models


class Lengua(models.Model):
    """Representa una lengua indígena en el sistema."""

    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lenguas'
        ordering = ['nombre']
        verbose_name = 'Lengua'
        verbose_name_plural = 'Lenguas'

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    def get_active_embedding(self):
        return self.embedding_versions.filter(status=EmbeddingVersion.STATUS_ACTIVE).first()


class TerminoEs(models.Model):
    """Término en español (entrada del diccionario en castellano)."""

    termino = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'terminos_es'
        ordering = ['termino']
        verbose_name = 'Término en Español'
        verbose_name_plural = 'Términos en Español'

    def __str__(self):
        return self.termino


class TerminoLeng(models.Model):
    """
    Término en lengua indígena.

    Cada registro pertenece a una lengua específica y puede estar vinculado
    a su equivalente en español (termino_es). La columna `definicion` contiene
    la descripción semántica del término en español.
    """

    termino_es = models.ForeignKey(
        TerminoEs,
        on_delete=models.SET_NULL,
        related_name='traducciones',
        null=True,
        blank=True,
    )
    lengua = models.ForeignKey(
        Lengua,
        on_delete=models.CASCADE,
        related_name='terminos',
        db_index=True,
    )
    termino = models.CharField(max_length=255, db_index=True)
    definicion = models.TextField(blank=True)
    pos = models.CharField(max_length=50, blank=True)
    sinonimos = models.JSONField(default=list, blank=True)
    ejemplos = models.JSONField(default=list, blank=True)
    tipo_morfema = models.CharField(max_length=50, null=True, blank=True)
    activo = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'terminos_leng'
        ordering = ['termino']
        unique_together = ('termino', 'lengua')
        verbose_name = 'Término en Lengua Indígena'
        verbose_name_plural = 'Términos en Lengua Indígena'

    def __str__(self):
        return f"{self.termino} [{self.lengua.codigo}]"


class EmbeddingVersion(models.Model):
    """
    Versión de embeddings generada para una lengua específica.

    El ciclo de vida de un embedding es:
      pending → generating → ready ←→ active
                           └→ failed
    """

    STATUS_PENDING = 'pending'
    STATUS_GENERATING = 'generating'
    STATUS_READY = 'ready'
    STATUS_ACTIVE = 'active'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_GENERATING, 'Generando'),
        (STATUS_READY, 'Listo'),
        (STATUS_ACTIVE, 'Activo'),
        (STATUS_FAILED, 'Fallido'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lengua = models.ForeignKey(
        Lengua,
        on_delete=models.CASCADE,
        related_name='embedding_versions',
        db_index=True,
    )
    version = models.CharField(max_length=50)
    model_name = models.CharField(max_length=255, default='intfloat/multilingual-e5-base')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    is_active = models.BooleanField(default=False, db_index=True)
    num_terminos = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    # Rutas en disco de los artefactos generados
    embeddings_path = models.CharField(max_length=500, blank=True)
    faiss_path = models.CharField(max_length=500, blank=True)
    metadata_path = models.CharField(max_length=500, blank=True)

    # Identificador del hilo/tarea background
    task_id = models.CharField(max_length=255, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'embedding_versions'
        ordering = ['-created_at']
        verbose_name = 'Versión de Embedding'
        verbose_name_plural = 'Versiones de Embeddings'

    def __str__(self):
        return f"{self.lengua.codigo} v{self.version} [{self.status}]"
