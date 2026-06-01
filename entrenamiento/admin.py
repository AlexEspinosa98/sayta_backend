from django.contrib import admin

from .models import ExperimentoEntrenamiento, ModeloAudio


@admin.register(ModeloAudio)
class ModeloAudioAdmin(admin.ModelAdmin):
    list_display = ('nombre_hf', 'tipo', 'descargado', 'created_at')
    list_filter = ('tipo', 'descargado')
    search_fields = ('nombre_hf',)


@admin.register(ExperimentoEntrenamiento)
class ExperimentoEntrenamientoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'lengua', 'modelo_base', 'estado', 'is_active', 'created_at')
    list_filter = ('estado', 'is_active', 'lengua')
    search_fields = ('nombre', 'mlflow_run_id')
    readonly_fields = ('id', 'created_at', 'completed_at', 'metricas', 'mlflow_run_id')
