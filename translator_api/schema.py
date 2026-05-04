_COMMUNITY_PARAM = {
    "name": "community",
    "in": "path",
    "required": True,
    "schema": {"type": "string", "enum": ["arhuaco", "arhueco", "iku", "kogui", "cogui"]},
    "description": "Nombre o alias de la comunidad.",
    "example": "arhuaco",
}

_SESSION_PARAM = {
    "name": "session",
    "in": "path",
    "required": True,
    "schema": {"type": "string"},
    "description": "Nombre exacto de la carpeta de jornada.",
    "example": "grabacion_10_04_26_sentencia",
}

_FILENAME_PARAM = {
    "name": "filename",
    "in": "path",
    "required": True,
    "schema": {"type": "string"},
    "description": "Nombre del archivo de audio incluyendo extensión.",
    "example": "audio1.mp3",
}

_JSON_CONTENT = "application/json"
_AUDIO_CONTENT = "audio/*"

OPENAPI_SCHEMA = {
    "openapi": "3.0.3",
    "info": {
        "title": "Sayta Backend API",
        "description": (
            "API para la traducción de la lengua Ette Taara y la gestión del corpus de "
            "grabaciones de las comunidades Arhuaco y Kogui.\n\n"
            "## Flujo del módulo de etiquetado\n"
            "1. `GET /api/grabaciones/` — ver comunidades disponibles\n"
            "2. `GET /api/grabaciones/{community}/` — ver jornadas de la comunidad\n"
            "3. `GET /api/grabaciones/{community}/{session}/audios/` — listar audios sin procesar\n"
            "4. `GET /api/grabaciones/{community}/{session}/audios/{filename}` — reproducir audio\n"
            "5. `GET /api/grabaciones/{community}/{session}/glosario/` — consultar glosario de referencia\n"
            "6. `POST /api/grabaciones/{community}/{session}/etiquetar/` — crear etiqueta para el audio\n"
            "7. `GET /api/grabaciones/{community}/{session}/estado/` — ver progreso de etiquetado\n"
        ),
        "version": "1.1.0",
    },
    "servers": [{"url": "/"}],
    "tags": [
        {"name": "Salud", "description": "Estado del servicio"},
        {"name": "Traducción", "description": "Pipeline de traducción Ette Taara ↔ Español"},
        {"name": "Grabaciones", "description": "Resumen y listado de comunidades y jornadas"},
        {"name": "Jornada", "description": "Detalle de audios, glosario y estado de una jornada"},
        {"name": "Etiquetado", "description": "CRUD de etiquetas para audios sin procesar"},
    ],
    "paths": {
        # ── Salud ──────────────────────────────────────────────────────────────
        "/health/": {
            "get": {
                "tags": ["Salud"],
                "summary": "Health check",
                "description": "Verifica que el servidor esté activo y respondiendo.",
                "operationId": "health_check",
                "responses": {
                    "200": {
                        "description": "Servicio disponible",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                                "example": {"message": "hola mundo"},
                            }
                        },
                    }
                },
            }
        },

        # ── Traducción ─────────────────────────────────────────────────────────
        "/api/traducir/": {
            "get": {
                "tags": ["Traducción"],
                "summary": "Ayuda del endpoint de traducción",
                "operationId": "translate_help",
                "responses": {
                    "200": {
                        "description": "Instrucciones de uso",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/TranslateHelp"}
                            }
                        },
                    }
                },
            },
            "post": {
                "tags": ["Traducción"],
                "summary": "Traducir frase a Ette Taara",
                "description": (
                    "Tokeniza la frase y ejecuta el pipeline: "
                    "guardrail → búsqueda semántica FAISS → fallback léxico."
                ),
                "operationId": "translate_phrase",
                "parameters": [
                    {
                        "name": "debug",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "enum": ["true", "1", "yes"]},
                        "description": "Activa modo debug.",
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        _JSON_CONTENT: {
                            "schema": {"$ref": "#/components/schemas/TranslateRequest"},
                            "examples": {
                                "simple": {"summary": "Palabra simple", "value": {"frase": "agua"}},
                                "debug": {"summary": "Con debug", "value": {"frase": "tierra", "debug": "true"}},
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Resultado de la traducción",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/TranslateResponse"},
                                "example": {
                                    "input": "agua",
                                    "tokens": ["agua"],
                                    "result": {
                                        "allowed": True,
                                        "guardrail": {"allowed": True, "flagged_tokens": [], "message": "OK"},
                                        "best_matches": [
                                            {
                                                "token": "agua",
                                                "lemma": "niria",
                                                "definicion": "agua, líquido",
                                                "pos": "NOM",
                                                "sinonimos": [],
                                                "score": 0.91,
                                            }
                                        ],
                                        "rendered_phrase": "niria: agua, líquido [NOM] (0.91)",
                                    },
                                },
                            }
                        },
                    },
                    "400": {"description": "JSON inválido o falta 'frase'", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    "405": {"description": "Método no permitido", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            },
        },

        # ── Grabaciones — raíz ────────────────────────────────────────────────
        "/api/grabaciones/debug/path/": {
            "get": {
                "tags": ["Grabaciones"],
                "summary": "Diagnóstico de ruta del servidor",
                "description": "Devuelve `pwd`, la ruta configurada y si existe en el sistema de archivos.",
                "operationId": "recordings_debug_path",
                "responses": {
                    "200": {
                        "description": "Diagnóstico de rutas",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/DebugPathResponse"},
                                "example": {
                                    "pwd": "/app",
                                    "grabaciones_base_path": "/mnt/sayta_data/data/Grabaciones",
                                    "existe": True,
                                    "contenido_mnt": ["sayta_data"],
                                    "pasos_cd_arriba": [{"nivel": 1, "path": "/", "contenido": ["app", "mnt"]}],
                                },
                            }
                        },
                    }
                },
            }
        },

        "/api/grabaciones/": {
            "get": {
                "tags": ["Grabaciones"],
                "summary": "Resumen de comunidades",
                "description": (
                    "Lista las comunidades (Arhuaco, Kogui) con total de jornadas, "
                    "archivos y duración total de audios sin procesar."
                ),
                "operationId": "recordings_root",
                "responses": {
                    "200": {
                        "description": "Resumen por comunidad",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/RecordingsRoot"},
                                "example": {
                                    "base_path": "/mnt/sayta_data/data/Grabaciones",
                                    "total_comunidades": 2,
                                    "comunidades": [
                                        {
                                            "comunidad": "Arhuaco",
                                            "total_jornadas": 2,
                                            "total_archivos": 45,
                                            "audios_sin_procesar": {
                                                "total_audios": 12,
                                                "duracion_segundos": 3720.5,
                                                "duracion_formateada": "1h 02m 00s",
                                                "sin_metadata": 0,
                                            },
                                        },
                                        {
                                            "comunidad": "Kogui",
                                            "total_jornadas": 2,
                                            "total_archivos": 38,
                                            "audios_sin_procesar": {
                                                "total_audios": 9,
                                                "duracion_segundos": 2890.0,
                                                "duracion_formateada": "0h 48m 10s",
                                                "sin_metadata": 0,
                                            },
                                        },
                                    ],
                                },
                            }
                        },
                    },
                    "404": {"description": "Ruta base no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            }
        },

        "/api/grabaciones/{community}/": {
            "get": {
                "tags": ["Grabaciones"],
                "summary": "Jornadas de grabación por comunidad",
                "description": (
                    "Devuelve las jornadas de la comunidad con fecha, temática, "
                    "total de ítems y estadísticas de audio. "
                    "Acepta alias: `arhuaco`, `arhueco`, `iku`, `kogui`, `cogui`."
                ),
                "operationId": "recordings_by_community",
                "parameters": [_COMMUNITY_PARAM],
                "responses": {
                    "200": {
                        "description": "Lista de jornadas",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/RecordingsByCommunity"},
                                "example": {
                                    "comunidad": "Arhuaco",
                                    "total_jornadas": 2,
                                    "resumen_audio": {
                                        "total_audios": 12,
                                        "duracion_formateada": "1h 02m 00s",
                                        "duracion_segundos": 3720.5,
                                    },
                                    "jornadas": [
                                        {
                                            "nombre": "grabacion_10_04_26_sentencia",
                                            "fecha_texto": "10/04/2026",
                                            "fecha_iso": "2026-04-10",
                                            "tematica": "sentencia",
                                            "total_items": 5,
                                            "audios_sin_procesar": {
                                                "total_audios": 6,
                                                "duracion_segundos": 1920.0,
                                                "duracion_formateada": "0h 32m 00s",
                                                "sin_metadata": 0,
                                            },
                                        },
                                        {
                                            "nombre": "grabacion_18_04_26_iku",
                                            "fecha_texto": "18/04/2026",
                                            "fecha_iso": "2026-04-18",
                                            "tematica": "iku",
                                            "total_items": 5,
                                            "audios_sin_procesar": {
                                                "total_audios": 6,
                                                "duracion_segundos": 1800.5,
                                                "duracion_formateada": "0h 30m 00s",
                                                "sin_metadata": 0,
                                            },
                                        },
                                    ],
                                },
                            }
                        },
                    },
                    "404": {"description": "Comunidad no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/CommunityNotFound"}}}},
                },
            }
        },

        # ── Jornada ────────────────────────────────────────────────────────────
        "/api/grabaciones/{community}/{session}/audios/": {
            "get": {
                "tags": ["Jornada"],
                "summary": "Listar audios sin procesar de una jornada",
                "description": (
                    "Devuelve todos los archivos de audio (`.wav`, `.mp3`, `.mp4`, `.ogg`, `.flac`) "
                    "dentro de `audios_sin_procesar/`, con duración y estado de etiquetado."
                ),
                "operationId": "session_audios",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM],
                "responses": {
                    "200": {
                        "description": "Lista de audios",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/SessionAudiosResponse"},
                                "example": {
                                    "comunidad": "arhuaco",
                                    "jornada": "grabacion_10_04_26_sentencia",
                                    "total_audios": 3,
                                    "audios": [
                                        {
                                            "nombre": "audio_001.mp3",
                                            "extension": ".mp3",
                                            "tamaño_bytes": 524288,
                                            "duracion_segundos": 32.4,
                                            "duracion_formateada": "0h 00m 32s",
                                            "etiquetado": True,
                                        },
                                        {
                                            "nombre": "audio_002.wav",
                                            "extension": ".wav",
                                            "tamaño_bytes": 1048576,
                                            "duracion_segundos": 58.1,
                                            "duracion_formateada": "0h 00m 58s",
                                            "etiquetado": False,
                                        },
                                        {
                                            "nombre": "audio_003.mp3",
                                            "extension": ".mp3",
                                            "tamaño_bytes": 262144,
                                            "duracion_segundos": 15.7,
                                            "duracion_formateada": "0h 00m 15s",
                                            "etiquetado": False,
                                        },
                                    ],
                                },
                            }
                        },
                    },
                    "404": {"description": "Comunidad o jornada no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            }
        },

        "/api/grabaciones/{community}/{session}/audios/{filename}": {
            "get": {
                "tags": ["Jornada"],
                "summary": "Reproducir archivo de audio",
                "description": (
                    "Devuelve el archivo de audio en streaming para ser reproducido directamente "
                    "en el frontend. Compatible con el elemento `<audio>` de HTML5 y cualquier "
                    "reproductor que soporte streaming HTTP."
                ),
                "operationId": "session_audio_file",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM, _FILENAME_PARAM],
                "responses": {
                    "200": {
                        "description": "Stream del archivo de audio",
                        "content": {
                            "audio/mpeg": {"schema": {"type": "string", "format": "binary"}},
                            "audio/wav": {"schema": {"type": "string", "format": "binary"}},
                            "audio/mp4": {"schema": {"type": "string", "format": "binary"}},
                        },
                    },
                    "404": {"description": "Archivo no encontrado", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            }
        },

        "/api/grabaciones/{community}/{session}/glosario/": {
            "get": {
                "tags": ["Jornada"],
                "summary": "Obtener glosario de la jornada",
                "description": (
                    "Devuelve el contenido completo del archivo `glosario.json` de la jornada. "
                    "Contiene términos en español con su traducción a la lengua indígena, "
                    "organizados por categorías temáticas."
                ),
                "operationId": "session_glosario",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM],
                "responses": {
                    "200": {
                        "description": "Glosario completo",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/GlosarioResponse"},
                                "example": {
                                    "metadata": {
                                        "titulo": "Glosario unificado Ikʉn / Iku (Arhuaco) – Bunachʉn (Español)",
                                        "fecha": "Unificación: mayo de 2026",
                                        "lengua_indigena": "ikʉn / iku (arhuaco)",
                                        "descripcion": "Glosario unificado a partir de dos fuentes complementarias.",
                                    },
                                    "categorias": [
                                        {
                                            "nombre": "Saludos",
                                            "terminos": [
                                                {"espanol": "Buenos días", "traduccion": "Du zari bunsi chano", "nota": None},
                                                {"espanol": "Gracias", "traduccion": "Du ni", "nota": None},
                                            ],
                                        }
                                    ],
                                },
                            }
                        },
                    },
                    "404": {"description": "glosario.json no encontrado", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            }
        },

        "/api/grabaciones/{community}/{session}/estado/": {
            "get": {
                "tags": ["Jornada"],
                "summary": "Estado de etiquetado de la jornada",
                "description": (
                    "Muestra qué audios ya tienen etiqueta (`.txt` en `audios_procesados/`) "
                    "y cuáles aún están pendientes, junto con el porcentaje de avance."
                ),
                "operationId": "session_estado",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM],
                "responses": {
                    "200": {
                        "description": "Estado de etiquetado",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/EstadoResponse"},
                                "example": {
                                    "comunidad": "arhuaco",
                                    "jornada": "grabacion_10_04_26_sentencia",
                                    "total_audios": 3,
                                    "total_etiquetados": 1,
                                    "total_sin_etiquetar": 2,
                                    "porcentaje_completado": 33.3,
                                    "etiquetados": [
                                        {
                                            "audio": "audio_001.mp3",
                                            "etiqueta": "Sakuku",
                                            "archivo_txt": "audio_001.txt",
                                        }
                                    ],
                                    "sin_etiquetar": ["audio_002.wav", "audio_003.mp3"],
                                },
                            }
                        },
                    },
                    "404": {"description": "Comunidad o jornada no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            }
        },

        # ── Etiquetado ────────────────────────────────────────────────────────
        "/api/grabaciones/{community}/{session}/etiquetar/": {
            "post": {
                "tags": ["Etiquetado"],
                "summary": "Crear etiqueta para un audio",
                "description": (
                    "Crea un archivo `.txt` en `audios_procesados/` con la etiqueta (palabra) "
                    "correspondiente al audio. El nombre del `.txt` es el mismo stem del audio "
                    "(ej. `audio_001.mp3` → `audio_001.txt`).\n\n"
                    "Devuelve `409` si ya existe etiqueta. Usar `PUT` para actualizar."
                ),
                "operationId": "session_etiquetar",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM],
                "requestBody": {
                    "required": True,
                    "content": {
                        _JSON_CONTENT: {
                            "schema": {"$ref": "#/components/schemas/EtiquetarRequest"},
                            "example": {
                                "nombre_audio": "audio_001.mp3",
                                "etiqueta": "Sakuku",
                            },
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Etiqueta creada correctamente",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/EtiquetarResponse"},
                                "example": {
                                    "mensaje": "Etiqueta creada.",
                                    "audio": "audio_001.mp3",
                                    "etiqueta": "Sakuku",
                                    "archivo_txt": "audio_001.txt",
                                },
                            }
                        },
                    },
                    "400": {"description": "Faltan campos requeridos o JSON inválido", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    "404": {"description": "Comunidad, jornada o audio no encontrado", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    "409": {
                        "description": "Ya existe etiqueta para este audio",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {"error": "Ya existe etiqueta para 'audio_001.mp3'. Usa PUT para actualizar."},
                            }
                        },
                    },
                },
            }
        },

        "/api/grabaciones/{community}/{session}/etiqueta/{filename}/": {
            "get": {
                "tags": ["Etiquetado"],
                "summary": "Leer etiqueta de un audio",
                "description": "Devuelve la etiqueta almacenada en el `.txt` correspondiente al audio.",
                "operationId": "session_etiqueta_get",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM, _FILENAME_PARAM],
                "responses": {
                    "200": {
                        "description": "Etiqueta del audio",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/EtiquetaResponse"},
                                "example": {
                                    "audio": "audio_001.mp3",
                                    "etiqueta": "Sakuku",
                                    "archivo_txt": "audio_001.txt",
                                },
                            }
                        },
                    },
                    "404": {"description": "Etiqueta no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            },
            "put": {
                "tags": ["Etiquetado"],
                "summary": "Actualizar etiqueta de un audio",
                "description": "Sobreescribe el `.txt` con la nueva etiqueta. Crea el archivo si no existe.",
                "operationId": "session_etiqueta_put",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM, _FILENAME_PARAM],
                "requestBody": {
                    "required": True,
                    "content": {
                        _JSON_CONTENT: {
                            "schema": {"$ref": "#/components/schemas/EtiquetaUpdateRequest"},
                            "example": {"etiqueta": "Sakʉn"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Etiqueta actualizada",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/EtiquetaResponse"},
                                "example": {
                                    "mensaje": "Etiqueta actualizada.",
                                    "audio": "audio_001.mp3",
                                    "etiqueta": "Sakʉn",
                                },
                            }
                        },
                    },
                    "400": {"description": "JSON inválido o falta 'etiqueta'", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                    "404": {"description": "Comunidad o jornada no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            },
            "delete": {
                "tags": ["Etiquetado"],
                "summary": "Eliminar etiqueta de un audio",
                "description": "Borra el archivo `.txt` de `audios_procesados/`, marcando el audio como sin etiquetar.",
                "operationId": "session_etiqueta_delete",
                "parameters": [_COMMUNITY_PARAM, _SESSION_PARAM, _FILENAME_PARAM],
                "responses": {
                    "200": {
                        "description": "Etiqueta eliminada",
                        "content": {
                            _JSON_CONTENT: {
                                "schema": {"$ref": "#/components/schemas/EtiquetaResponse"},
                                "example": {
                                    "mensaje": "Etiqueta eliminada.",
                                    "audio": "audio_001.mp3",
                                },
                            }
                        },
                    },
                    "404": {"description": "Etiqueta no encontrada", "content": {_JSON_CONTENT: {"schema": {"$ref": "#/components/schemas/Error"}}}},
                },
            },
        },
    },

    # ── Schemas ────────────────────────────────────────────────────────────────
    "components": {
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {"error": {"type": "string", "example": "Recurso no encontrado."}},
            },
            "HealthResponse": {
                "type": "object",
                "properties": {"message": {"type": "string", "example": "hola mundo"}},
            },
            "DebugPathResponse": {
                "type": "object",
                "properties": {
                    "pwd": {"type": "string", "example": "/app"},
                    "grabaciones_base_path": {"type": "string", "example": "/mnt/sayta_data/data/Grabaciones"},
                    "existe": {"type": "boolean", "example": True},
                    "contenido_mnt": {"type": "array", "items": {"type": "string"}, "example": ["sayta_data"]},
                    "pasos_cd_arriba": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nivel": {"type": "integer"},
                                "path": {"type": "string"},
                                "contenido": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
            "TranslateHelp": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "example": {"type": "object", "properties": {"frase": {"type": "string"}}},
                },
            },
            "TranslateRequest": {
                "type": "object",
                "required": ["frase"],
                "properties": {
                    "frase": {"type": "string", "example": "agua"},
                    "debug": {"type": "string", "example": "true"},
                },
            },
            "Match": {
                "type": "object",
                "properties": {
                    "token": {"type": "string", "example": "agua"},
                    "lemma": {"type": "string", "example": "niria"},
                    "definicion": {"type": "string", "example": "agua, líquido"},
                    "pos": {"type": "string", "example": "NOM"},
                    "sinonimos": {"type": "array", "items": {"type": "string"}},
                    "score": {"type": "number", "format": "float", "example": 0.91},
                    "fallback": {"type": "boolean"},
                },
            },
            "Guardrail": {
                "type": "object",
                "properties": {
                    "allowed": {"type": "boolean"},
                    "flagged_tokens": {"type": "array", "items": {"type": "string"}},
                    "message": {"type": "string", "example": "OK"},
                },
            },
            "PipelineResult": {
                "type": "object",
                "properties": {
                    "allowed": {"type": "boolean"},
                    "guardrail": {"$ref": "#/components/schemas/Guardrail"},
                    "best_matches": {"type": "array", "items": {"$ref": "#/components/schemas/Match"}},
                    "rendered_phrase": {"type": "string", "example": "niria: agua, líquido [NOM] (0.91)"},
                },
            },
            "TranslateResponse": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "tokens": {"type": "array", "items": {"type": "string"}},
                    "result": {"$ref": "#/components/schemas/PipelineResult"},
                },
            },
            "AudioStats": {
                "type": "object",
                "properties": {
                    "total_audios": {"type": "integer", "example": 6},
                    "duracion_segundos": {"type": "number", "format": "float", "example": 1920.0},
                    "duracion_formateada": {"type": "string", "example": "0h 32m 00s"},
                    "sin_metadata": {"type": "integer", "example": 0, "description": "Audios sin metadatos de duración legibles"},
                },
            },
            "CommunitySummary": {
                "type": "object",
                "properties": {
                    "comunidad": {"type": "string", "example": "Arhuaco"},
                    "total_jornadas": {"type": "integer", "example": 2},
                    "total_archivos": {"type": "integer", "example": 45},
                    "audios_sin_procesar": {"$ref": "#/components/schemas/AudioStats"},
                },
            },
            "RecordingsRoot": {
                "type": "object",
                "properties": {
                    "base_path": {"type": "string", "example": "/mnt/sayta_data/data/Grabaciones"},
                    "total_comunidades": {"type": "integer", "example": 2},
                    "comunidades": {"type": "array", "items": {"$ref": "#/components/schemas/CommunitySummary"}},
                },
            },
            "JornadaSummary": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "example": "grabacion_10_04_26_sentencia"},
                    "fecha_texto": {"type": "string", "example": "10/04/2026", "nullable": True},
                    "fecha_iso": {"type": "string", "format": "date", "example": "2026-04-10", "nullable": True},
                    "tematica": {"type": "string", "example": "sentencia", "nullable": True},
                    "total_items": {"type": "integer", "example": 5},
                    "audios_sin_procesar": {"$ref": "#/components/schemas/AudioStats"},
                },
            },
            "RecordingsByCommunity": {
                "type": "object",
                "properties": {
                    "comunidad": {"type": "string", "example": "Arhuaco"},
                    "total_jornadas": {"type": "integer", "example": 2},
                    "resumen_audio": {"$ref": "#/components/schemas/AudioStats"},
                    "jornadas": {"type": "array", "items": {"$ref": "#/components/schemas/JornadaSummary"}},
                },
            },
            "CommunityNotFound": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "No se encontró la comunidad 'xyz'."},
                    "comunidades_disponibles": {"type": "array", "items": {"type": "string"}, "example": ["Arhuaco", "Kogui"]},
                },
            },
            "AudioItem": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "example": "audio_001.mp3"},
                    "extension": {"type": "string", "example": ".mp3"},
                    "tamaño_bytes": {"type": "integer", "example": 524288},
                    "duracion_segundos": {"type": "number", "format": "float", "example": 32.4, "nullable": True},
                    "duracion_formateada": {"type": "string", "example": "0h 00m 32s", "nullable": True},
                    "etiquetado": {"type": "boolean", "example": False},
                },
            },
            "SessionAudiosResponse": {
                "type": "object",
                "properties": {
                    "comunidad": {"type": "string", "example": "arhuaco"},
                    "jornada": {"type": "string", "example": "grabacion_10_04_26_sentencia"},
                    "total_audios": {"type": "integer", "example": 3},
                    "audios": {"type": "array", "items": {"$ref": "#/components/schemas/AudioItem"}},
                },
            },
            "GlosarioTermino": {
                "type": "object",
                "properties": {
                    "espanol": {"type": "string", "example": "Cabeza"},
                    "traduccion": {"type": "string", "example": "Sakuku"},
                    "nota": {"type": "string", "example": "Variante: Sakʉn", "nullable": True},
                },
            },
            "GlosarioCategoria": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "example": "Anatomía / Partes del cuerpo"},
                    "terminos": {"type": "array", "items": {"$ref": "#/components/schemas/GlosarioTermino"}},
                },
            },
            "GlosarioMetadata": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "fecha": {"type": "string"},
                    "lengua_indigena": {"type": "string"},
                    "descripcion": {"type": "string"},
                },
            },
            "GlosarioResponse": {
                "type": "object",
                "properties": {
                    "metadata": {"$ref": "#/components/schemas/GlosarioMetadata"},
                    "categorias": {"type": "array", "items": {"$ref": "#/components/schemas/GlosarioCategoria"}},
                },
            },
            "EtiquetarRequest": {
                "type": "object",
                "required": ["nombre_audio", "etiqueta"],
                "properties": {
                    "nombre_audio": {"type": "string", "example": "audio_001.mp3", "description": "Nombre del archivo de audio incluyendo extensión"},
                    "etiqueta": {"type": "string", "example": "Sakuku", "description": "Palabra o transcripción en lengua indígena"},
                },
            },
            "EtiquetarResponse": {
                "type": "object",
                "properties": {
                    "mensaje": {"type": "string", "example": "Etiqueta creada."},
                    "audio": {"type": "string", "example": "audio_001.mp3"},
                    "etiqueta": {"type": "string", "example": "Sakuku"},
                    "archivo_txt": {"type": "string", "example": "audio_001.txt"},
                },
            },
            "EtiquetaResponse": {
                "type": "object",
                "properties": {
                    "audio": {"type": "string", "example": "audio_001.mp3"},
                    "etiqueta": {"type": "string", "example": "Sakuku"},
                    "archivo_txt": {"type": "string", "example": "audio_001.txt"},
                },
            },
            "EtiquetaUpdateRequest": {
                "type": "object",
                "required": ["etiqueta"],
                "properties": {
                    "etiqueta": {"type": "string", "example": "Sakʉn"},
                },
            },
            "EtiquetadoItem": {
                "type": "object",
                "properties": {
                    "audio": {"type": "string", "example": "audio_001.mp3"},
                    "etiqueta": {"type": "string", "example": "Sakuku"},
                    "archivo_txt": {"type": "string", "example": "audio_001.txt"},
                },
            },
            "EstadoResponse": {
                "type": "object",
                "properties": {
                    "comunidad": {"type": "string", "example": "arhuaco"},
                    "jornada": {"type": "string", "example": "grabacion_10_04_26_sentencia"},
                    "total_audios": {"type": "integer", "example": 3},
                    "total_etiquetados": {"type": "integer", "example": 1},
                    "total_sin_etiquetar": {"type": "integer", "example": 2},
                    "porcentaje_completado": {"type": "number", "format": "float", "example": 33.3},
                    "etiquetados": {"type": "array", "items": {"$ref": "#/components/schemas/EtiquetadoItem"}},
                    "sin_etiquetar": {"type": "array", "items": {"type": "string"}, "example": ["audio_002.wav", "audio_003.mp3"]},
                },
            },
        }
    },
}
