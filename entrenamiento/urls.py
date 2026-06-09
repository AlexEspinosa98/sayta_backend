from django.urls import path

from .views import (
    AugmentationCatalogoView,
    DatasetComunidadView,
    DatasetEstadoView,
    DatasetSesionesView,
    EntrenarView,
    EstadisticasGrabacionesView,
    ExperimentoActivarView,
    ExperimentoCancelarView,
    ExperimentoDetailView,
    ExperimentoEstadoView,
    ExperimentoListView,
    LenguasEntrenamientoView,
    ModeloDescargarView,
    ModeloListView,
    ModelosDisponiblesView,
    SistemaLiberarMemoriaView,
    SistemaView,
    SubirAudioView,
    TranscribirTraducirView,
    TranscribirView,
)

urlpatterns = [
    # Estado del sistema
    path('sistema/', SistemaView.as_view(), name='entrenamiento_sistema'),
    path('sistema/liberar-memoria/', SistemaLiberarMemoriaView.as_view(), name='entrenamiento_liberar_memoria'),

    # Lenguas con estado ASR
    path('lenguas/', LenguasEntrenamientoView.as_view(), name='entrenamiento_lenguas'),

    # Catálogo y gestión de modelos
    path('modelos-disponibles/', ModelosDisponiblesView.as_view(), name='entrenamiento_modelos_disponibles'),
    path('modelos/', ModeloListView.as_view(), name='entrenamiento_modelos'),
    path('modelos/descargar/', ModeloDescargarView.as_view(), name='entrenamiento_modelos_descargar'),

    # Dataset — datos etiquetados
    # IMPORTANTE: rutas fijas ('sesiones/', 'subir/', 'estadisticas/', 'augmentation/')
    # deben ir ANTES del parámetro <str:community>/
    path('dataset/', DatasetEstadoView.as_view(), name='entrenamiento_dataset'),
    path('dataset/sesiones/', DatasetSesionesView.as_view(), name='entrenamiento_dataset_sesiones'),
    path('dataset/subir/', SubirAudioView.as_view(), name='entrenamiento_dataset_subir'),
    path('dataset/estadisticas/', EstadisticasGrabacionesView.as_view(), name='entrenamiento_dataset_estadisticas'),
    path('dataset/augmentation/', AugmentationCatalogoView.as_view(), name='entrenamiento_augmentation_catalogo'),
    path('dataset/<str:community>/', DatasetComunidadView.as_view(), name='entrenamiento_dataset_comunidad'),

    # Lanzar entrenamiento
    path('entrenar/', EntrenarView.as_view(), name='entrenamiento_entrenar'),

    # Experimentos
    path('experimentos/', ExperimentoListView.as_view(), name='entrenamiento_experimentos'),
    path('experimentos/<uuid:pk>/', ExperimentoDetailView.as_view(), name='entrenamiento_experimento_detail'),
    path('experimentos/<uuid:pk>/estado/', ExperimentoEstadoView.as_view(), name='entrenamiento_experimento_estado'),
    path('experimentos/<uuid:pk>/cancelar/', ExperimentoCancelarView.as_view(), name='entrenamiento_experimento_cancelar'),
    path('experimentos/<uuid:pk>/activar/', ExperimentoActivarView.as_view(), name='entrenamiento_experimento_activar'),

    # Transcripción con modelo activo (integración con pipeline de traducción)
    path('transcribir/', TranscribirView.as_view(), name='entrenamiento_transcribir'),
    path('transcribir-y-traducir/', TranscribirTraducirView.as_view(), name='entrenamiento_transcribir_traducir'),
]
