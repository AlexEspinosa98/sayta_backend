"""
Django settings for sayta_backend project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-zigk3rl!7shnqxtgp!*_l(2iuerunrrcjx_!!*wt*%$($)39h^',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Terceros
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    # Propias
    'health',
    'translator_api',
    'terminos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sayta_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sayta_backend.wsgi.application'

# ---------------------------------------------------------------------------
# Base de datos — PostgreSQL
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'sayta_db'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '60')),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Sayta — API de Términos y Embeddings',
    'DESCRIPTION': (
        'API REST para gestionar diccionarios de lenguas indígenas colombianas.\n\n'
        '**Flujo recomendado:**\n'
        '1. Crear lengua → `POST /api/terminos/lenguas/`\n'
        '2. Cargar términos → `POST /api/terminos/terminos/carga-masiva/`\n'
        '3. Generar embeddings → `POST /api/terminos/embeddings/generar/`\n'
        '4. Monitorear → `GET /api/terminos/embeddings/estado/{task_id}/`\n'
        '5. Activar → `POST /api/terminos/embeddings/{id}/activar/`\n'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'TAGS': [
        {'name': 'Lenguas', 'description': 'Gestión de lenguas indígenas registradas'},
        {'name': 'Términos ES', 'description': 'Términos en español (entradas del diccionario)'},
        {'name': 'Términos Lengua', 'description': 'Términos en lengua indígena con definición'},
        {'name': 'Embeddings', 'description': 'Generación, activación y monitoreo de embeddings por lengua'},
    ],
}

# ---------------------------------------------------------------------------
# Validadores de contraseña
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'terminos': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'translator_api': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Embeddings — configuración de directorios
# ---------------------------------------------------------------------------

# Artefactos legacy del traductor Ette (faiss_index.bin, metadata.json, embeddings.npy)
ETTE_EMBEDDINGS_DIR = BASE_DIR / 'translator_api' / 'embeddings'

# Directorio raíz donde se almacenan los embeddings generados desde la BD.
# Estructura: EMBEDDINGS_STORAGE_DIR / <codigo_lengua> / <version> / {embeddings.npy, faiss_index.bin, metadata.json}
EMBEDDINGS_STORAGE_DIR = os.environ.get(
    'EMBEDDINGS_STORAGE_DIR',
    str(BASE_DIR / 'embeddings_storage'),
)

# Modelo HuggingFace por defecto para generación de embeddings
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'intfloat/multilingual-e5-base')
