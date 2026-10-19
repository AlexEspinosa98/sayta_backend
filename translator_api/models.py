from django.conf import settings
from django.db import models
from django.utils import timezone

# Create your models here.


class EtiquetaHistorial(models.Model):
    """
    Historial de cambios de las etiquetas de audio: quién las creó, quién las editó
    (con el texto anterior y el nuevo) y quién las eliminó. La etiqueta vigente sigue
    viviendo en el archivo .txt de la jornada; esta tabla guarda el rastro de autoría.
    """

    ACCIONES = [('crear', 'Creó'), ('editar', 'Editó'), ('eliminar', 'Eliminó')]
    ORIGENES = [('app', 'Registrado al guardar'), ('auditoria', 'Reconstruido desde la auditoría')]

    comunidad = models.CharField(max_length=100, db_index=True)
    jornada = models.CharField(max_length=200, db_index=True)
    audio = models.CharField(max_length=255)
    accion = models.CharField(max_length=10, choices=ACCIONES)
    etiqueta_anterior = models.TextField(blank=True, default='')
    etiqueta_nueva = models.TextField(blank=True, default='')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='etiquetas_historial',
    )
    usuario_nombre = models.CharField(max_length=150, blank=True, default='')
    origen = models.CharField(max_length=10, choices=ORIGENES, default='app')
    # True cuando el autor se dedujo cruzando la hora del archivo con la auditoría (no es exacto).
    aproximado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'etiquetas_historial'
        ordering = ['-creado_en', '-id']
        indexes = [models.Index(fields=['comunidad', 'jornada', 'audio'])]
        verbose_name = 'Historial de etiqueta'
        verbose_name_plural = 'Historial de etiquetas'

    def __str__(self):
        return f'{self.accion} {self.comunidad}/{self.jornada}/{self.audio} por {self.usuario_nombre or "?"}'
