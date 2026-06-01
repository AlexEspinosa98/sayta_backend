"""
Settings de producción para el entorno Docker.

Hereda de settings.py y sobreescribe únicamente lo que difiere en producción.
El docker-compose inyecta todas las variables de entorno necesarias.
"""

from .settings import *  # noqa: F401, F403

import os

# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------

DEBUG = False

# En producción el proxy nginx es el punto de entrada; el backend solo
# recibe conexiones internas, pero se mantiene el host configurado.
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')

CSRF_TRUSTED_ORIGINS = [
    h.strip()
    for h in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if h.strip()
]

# ---------------------------------------------------------------------------
# Base de datos — mismas vars POSTGRES_* que usa docker-compose
# ---------------------------------------------------------------------------
# (ya heredadas de settings.py con los nombres correctos)

# Más conexiones persistentes en producción
DATABASES['default']['CONN_MAX_AGE'] = int(os.environ.get('DB_CONN_MAX_AGE', '300'))

# ---------------------------------------------------------------------------
# Embeddings y modelos HuggingFace — rutas dentro del contenedor
# ---------------------------------------------------------------------------

# Artefactos Ette legacy (copiados en imagen Docker con COPY)
ETTE_EMBEDDINGS_DIR = os.environ.get(
    'ETTE_EMBEDDINGS_DIR',
    '/app/translator_api/embeddings',
)

# Almacenamiento de embeddings generados desde BD (volumen NVMe)
EMBEDDINGS_STORAGE_DIR = os.environ.get(
    'EMBEDDINGS_STORAGE_DIR',
    '/mnt/app_storage/embeddings_storage',
)

# Caché de modelos HuggingFace (volumen NVMe persistente)
os.environ.setdefault('HF_HOME', os.environ.get('HF_HOME', '/mnt/models'))
os.environ.setdefault('TRANSFORMERS_CACHE', os.environ.get('TRANSFORMERS_CACHE', '/mnt/models/transformers'))

# ---------------------------------------------------------------------------
# Módulo de entrenamiento ASR — rutas en volumen NVMe
# ---------------------------------------------------------------------------

AUDIO_MODELS_DIR = os.environ.get(
    'AUDIO_MODELS_DIR',
    '/mnt/app_storage/audio_models',
)

MODELOS_ENTRENADOS_DIR = os.environ.get(
    'MODELOS_ENTRENADOS_DIR',
    '/mnt/app_storage/modelos_entrenados',
)

MLFLOW_TRACKING_URI = os.environ.get(
    'MLFLOW_TRACKING_URI',
    '/mnt/app_storage/mlruns',
)

# Logger del módulo de entrenamiento
LOGGING['loggers']['entrenamiento'] = {
    'handlers': ['console'],
    'level': 'INFO',
    'propagate': False,
}

# ---------------------------------------------------------------------------
# Archivos estáticos
# ---------------------------------------------------------------------------

STATIC_ROOT = '/mnt/app_storage/staticfiles'

# ---------------------------------------------------------------------------
# Logging en producción
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'production': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'production',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'terminos': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'translator_api': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}
