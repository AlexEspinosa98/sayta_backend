import uuid

from django.conf import settings
from django.db import models


class ConsultaTraduccion(models.Model):
    """
    Registro de cada traducción pedida: qué se consultó, qué respondió el sistema y con qué
    confianza. Sirve para saber qué falta en el glosario (consultas sin coincidencia frecuentes)
    y para medir el traductor con uso real.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lengua = models.ForeignKey('terminos.Lengua', on_delete=models.CASCADE, related_name='consultas_traduccion')
    direccion = models.CharField(max_length=20)                     # es_a_lengua | lengua_a_es
    origen = models.CharField(max_length=20, default='texto')       # texto | audio
    texto = models.TextField()
    texto_normalizado = models.CharField(max_length=500, db_index=True, blank=True)
    mejor_termino = models.CharField(max_length=500, blank=True)
    mejor_termino_es = models.CharField(max_length=500, blank=True)
    confianza = models.IntegerField(null=True, blank=True)
    nivel = models.CharField(max_length=20, blank=True)
    fuente = models.CharField(max_length=20, blank=True)
    en_glosario = models.BooleanField(default=False, db_index=True)
    verificacion_estado = models.CharField(max_length=30, blank=True)
    verificacion_ms = models.IntegerField(null=True, blank=True)
    ms_total = models.IntegerField(null=True, blank=True)
    eleccion_usuario = models.IntegerField(null=True, blank=True)   # índice elegido si cambió la opción
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='consultas_traduccion')
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'traduccion_consultas'
        ordering = ['-creado_en']
        verbose_name = 'Consulta de traducción'
        verbose_name_plural = 'Consultas de traducción'

    def __str__(self):
        return f'{self.lengua.codigo} {self.direccion}: {self.texto[:40]}'


class CorreccionTraduccion(models.Model):
    """
    Correcciones y validaciones hechas por personas:
      - correccion:          «la traducción está mal; la correcta es …» (desde el traductor)
      - validacion_hipotesis: veredicto sobre un término marcado como hipótesis (tipo_morfema='hipótesis')
      - validacion_compuesta: veredicto sobre una traducción compuesta por el verificador
    Quedan pendientes hasta que alguien con permiso de edición del glosario las revisa; al aprobarlas
    pueden aplicarse al glosario (crear o actualizar el término).
    """
    TIPOS = [('correccion', 'Corrección'), ('validacion_hipotesis', 'Validación de hipótesis'), ('validacion_compuesta', 'Validación de traducción compuesta')]
    VEREDICTOS = [('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('rechazada', 'Rechazada')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=30, choices=TIPOS, default='correccion', db_index=True)
    consulta = models.ForeignKey(ConsultaTraduccion, null=True, blank=True, on_delete=models.SET_NULL, related_name='correcciones')
    lengua = models.ForeignKey('terminos.Lengua', on_delete=models.CASCADE, related_name='correcciones_traduccion')
    termino = models.ForeignKey('terminos.TerminoLeng', null=True, blank=True, on_delete=models.SET_NULL, related_name='correcciones')
    direccion = models.CharField(max_length=20, blank=True)
    texto_origen = models.TextField(blank=True)
    propuesta_sistema = models.TextField(blank=True)
    correccion = models.TextField(blank=True)          # texto correcto según la persona (vacío si solo valida)
    es_correcta = models.BooleanField(null=True, blank=True)   # para validaciones: ¿la propuesta del sistema es correcta?
    comentario = models.TextField(blank=True)
    veredicto = models.CharField(max_length=20, choices=VEREDICTOS, default='pendiente', db_index=True)
    aplicada = models.BooleanField(default=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='correcciones_traduccion')
    usuario_nombre = models.CharField(max_length=150, blank=True)
    revisor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='correcciones_revisadas')
    revisado_en = models.DateTimeField(null=True, blank=True)
    nota_revision = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'traduccion_correcciones'
        ordering = ['-creado_en']
        verbose_name = 'Corrección de traducción'
        verbose_name_plural = 'Correcciones de traducción'

    def __str__(self):
        return f'{self.tipo} [{self.veredicto}] {self.texto_origen[:40]}'


class HistorialTermino(models.Model):
    """Quién creó, editó, restauró o borró cada término del glosario, con el antes y el después."""
    ACCIONES = [('crear', 'Creó'), ('editar', 'Editó'), ('eliminar', 'Eliminó'), ('restaurar', 'Restauró'), ('desactivar', 'Desactivó')]
    termino = models.ForeignKey('terminos.TerminoLeng', null=True, blank=True, on_delete=models.SET_NULL, related_name='historial')
    termino_id_original = models.IntegerField(null=True, blank=True, db_index=True)
    termino_texto = models.CharField(max_length=255, blank=True)
    lengua_codigo = models.CharField(max_length=20, blank=True, db_index=True)
    accion = models.CharField(max_length=12, choices=ACCIONES, db_index=True)
    cambios = models.JSONField(default=dict)      # {campo: {"antes": ..., "despues": ...}}
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='cambios_glosario')
    usuario_nombre = models.CharField(max_length=150, blank=True)
    origen = models.CharField(max_length=30, blank=True)   # api | carga_masiva | correccion | shell
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'traduccion_historial_terminos'
        ordering = ['-creado_en', '-id']
        verbose_name = 'Historial de término'
        verbose_name_plural = 'Historial de términos'

    def __str__(self):
        return f'{self.accion} {self.termino_texto} ({self.usuario_nombre or "sistema"})'
