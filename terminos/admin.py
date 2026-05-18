from django.contrib import admin

from .models import EmbeddingVersion, Lengua, TerminoEs, TerminoLeng


@admin.register(Lengua)
class LenguaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'codigo', 'activa', 'created_at']
    list_filter = ['activa']
    search_fields = ['nombre', 'codigo']
    ordering = ['nombre']


@admin.register(TerminoEs)
class TerminoEsAdmin(admin.ModelAdmin):
    list_display = ['termino', 'created_at']
    search_fields = ['termino']
    ordering = ['termino']


@admin.register(TerminoLeng)
class TerminoLengAdmin(admin.ModelAdmin):
    list_display = ['termino', 'lengua', 'termino_es', 'pos', 'activo', 'created_at']
    list_filter = ['lengua', 'activo', 'pos']
    search_fields = ['termino', 'definicion']
    ordering = ['termino']
    autocomplete_fields = ['termino_es']
    list_select_related = ['lengua', 'termino_es']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('lengua', 'termino_es')


@admin.register(EmbeddingVersion)
class EmbeddingVersionAdmin(admin.ModelAdmin):
    list_display = ['lengua', 'version', 'status', 'is_active', 'num_terminos', 'created_at', 'completed_at']
    list_filter = ['lengua', 'status', 'is_active']
    readonly_fields = [
        'id', 'task_id', 'status', 'num_terminos',
        'embeddings_path', 'faiss_path', 'metadata_path',
        'created_at', 'completed_at', 'error_message',
    ]
    ordering = ['-created_at']
