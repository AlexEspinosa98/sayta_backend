from django.urls import path

from .views import (
    DatasetComunidadView,
    DatasetEstadoView,
    DatasetSesionesView,
    EntrenarView,
    ExperimentoActivarView,
    ExperimentoDetailView,
    ExperimentoEstadoView,
    ExperimentoListView,
    LenguasEntrenamientoView,
    ModeloDescargarView,
    ModeloListView,
    ModelosDisponiblesView,
    TranscribirTraducirView,
    TranscribirView,
)

urlpatterns = [
    # Lenguas con estado ASR
    path('lenguas/', LenguasEntrenamientoView.as_view(), name='entrenamiento_lenguas'),

    # Catálogo y gestión de modelos
    path('modelos-disponibles/', ModelosDisponiblesView.as_view(), name='entrenamiento_modelos_disponibles'),
    path('modelos/', ModeloListView.as_view(), name='entrenamiento_modelos'),
    path('modelos/descargar/', ModeloDescargarView.as_view(), name='entrenamiento_modelos_descargar'),

    # Dataset — datos etiquetados
    # IMPORTANTE: 'sesiones/' debe ir ANTES del parámetro <str:community>/
    path('dataset/', DatasetEstadoView.as_view(), name='entrenamiento_dataset'),
    path('dataset/sesiones/', DatasetSesionesView.as_view(), name='entrenamiento_dataset_sesiones'),
    path('dataset/<str:community>/', DatasetComunidadView.as_view(), name='entrenamiento_dataset_comunidad'),

    # Lanzar entrenamiento
    path('entrenar/', EntrenarView.as_view(), name='entrenamiento_entrenar'),

    # Experimentos
    path('experimentos/', ExperimentoListView.as_view(), name='entrenamiento_experimentos'),
    path('experimentos/<uuid:pk>/', ExperimentoDetailView.as_view(), name='entrenamiento_experimento_detail'),
    path('experimentos/<uuid:pk>/estado/', ExperimentoEstadoView.as_view(), name='entrenamiento_experimento_estado'),
    path('experimentos/<uuid:pk>/activar/', ExperimentoActivarView.as_view(), name='entrenamiento_experimento_activar'),

    # Transcripción con modelo activo (integración con pipeline de traducción)
    path('transcribir/', TranscribirView.as_view(), name='entrenamiento_transcribir'),
    path('transcribir-y-traducir/', TranscribirTraducirView.as_view(), name='entrenamiento_transcribir_traducir'),
]
