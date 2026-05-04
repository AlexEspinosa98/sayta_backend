OPENAPI_SCHEMA = {
    "openapi": "3.0.3",
    "info": {
        "title": "Sayta Backend API",
        "description": (
            "API para la traducción de la lengua Ette Taara y la gestión del "
            "corpus de grabaciones de las comunidades Arhuaco y Kogui."
        ),
        "version": "1.0.0",
    },
    "servers": [{"url": "/"}],
    "tags": [
        {"name": "Salud", "description": "Estado del servicio"},
        {"name": "Traducción", "description": "Pipeline de traducción Ette Taara ↔ Español"},
        {"name": "Grabaciones", "description": "Corpus de audio por comunidad"},
    ],
    "paths": {
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
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {"type": "string", "example": "hola mundo"}
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/traducir/": {
            "get": {
                "tags": ["Traducción"],
                "summary": "Ayuda del endpoint de traducción",
                "description": "Devuelve instrucciones de uso y un ejemplo.",
                "operationId": "translate_help",
                "responses": {
                    "200": {
                        "description": "Instrucciones de uso",
                        "content": {
                            "application/json": {
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
                    "Recibe una frase en español, la tokeniza y ejecuta el pipeline "
                    "de traducción: guardrail → búsqueda semántica (FAISS) → fallback léxico."
                ),
                "operationId": "translate_phrase",
                "parameters": [
                    {
                        "name": "debug",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "enum": ["true", "1", "yes"]},
                        "description": "Activa el modo debug para inspeccionar tokens y matches internos.",
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TranslateRequest"},
                            "examples": {
                                "simple": {
                                    "summary": "Frase simple",
                                    "value": {"frase": "agua"},
                                },
                                "debug": {
                                    "summary": "Con modo debug",
                                    "value": {"frase": "tierra", "debug": "true"},
                                },
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Resultado de la traducción",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TranslateResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Falta el campo 'frase' o JSON inválido",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        },
                    },
                    "405": {
                        "description": "Método no permitido",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        },
                    },
                },
            },
        },
        "/api/grabaciones/debug/path/": {
            "get": {
                "tags": ["Grabaciones"],
                "summary": "Diagnóstico de ruta de grabaciones",
                "description": (
                    "Devuelve el directorio de trabajo actual del servidor (`pwd`), "
                    "la ruta configurada para las grabaciones y si dicha ruta existe en el sistema de archivos."
                ),
                "operationId": "recordings_debug_path",
                "responses": {
                    "200": {
                        "description": "Información de rutas del servidor",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "pwd": {
                                            "type": "string",
                                            "example": "/home/user/sayta_backend",
                                        },
                                        "grabaciones_base_path": {
                                            "type": "string",
                                            "example": "/mnt/sayta_data/data/Grabaciones",
                                        },
                                        "existe": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/grabaciones/": {
            "get": {
                "tags": ["Grabaciones"],
                "summary": "Resumen de comunidades y grabaciones",
                "description": (
                    "Lista las comunidades disponibles (Arhuaco, Kogui) con el número "
                    "de sesiones de grabación y archivos totales."
                ),
                "operationId": "recordings_root",
                "responses": {
                    "200": {
                        "description": "Resumen por comunidad",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RecordingsRoot"}
                            }
                        },
                    },
                    "404": {
                        "description": "Ruta base no encontrada o sin carpetas",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"}
                            }
                        },
                    },
                },
            }
        },
        "/api/grabaciones/{community}/": {
            "get": {
                "tags": ["Grabaciones"],
                "summary": "Sesiones de grabación por comunidad",
                "description": (
                    "Devuelve las sesiones de grabación de una comunidad con nombre y fecha. "
                    "Acepta alias: `arhuaco`, `arhueco`, `iku`, `kogui`, `cogui`."
                ),
                "operationId": "recordings_by_community",
                "parameters": [
                    {
                        "name": "community",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                            "enum": ["arhuaco", "arhueco", "iku", "kogui", "cogui"],
                        },
                        "description": "Nombre o alias de la comunidad.",
                        "example": "kogui",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Lista de sesiones",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RecordingsByCommunity"}
                            }
                        },
                    },
                    "404": {
                        "description": "Comunidad no encontrada",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CommunityNotFound"}
                            }
                        },
                    },
                },
            }
        },
    },
    "components": {
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "example": "Falta el campo 'frase'"}
                },
            },
            "TranslateHelp": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "example": "Envía la frase vía POST en el campo 'frase'",
                    },
                    "example": {
                        "type": "object",
                        "properties": {
                            "frase": {"type": "string", "example": "hola mundo"}
                        },
                    },
                },
            },
            "TranslateRequest": {
                "type": "object",
                "required": ["frase"],
                "properties": {
                    "frase": {
                        "type": "string",
                        "description": "Frase o palabra a traducir",
                        "example": "agua",
                    },
                    "debug": {
                        "type": "string",
                        "description": "Activa modo debug ('true', '1', 'yes')",
                        "example": "true",
                    },
                },
            },
            "Match": {
                "type": "object",
                "properties": {
                    "token": {"type": "string", "example": "agua"},
                    "lemma": {"type": "string", "example": "niria"},
                    "definicion": {"type": "string", "example": "agua, líquido"},
                    "pos": {"type": "string", "example": "NOM"},
                    "sinonimos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["niria"],
                    },
                    "score": {"type": "number", "format": "float", "example": 0.87},
                    "fallback": {
                        "type": "boolean",
                        "description": "True si el resultado viene de búsqueda léxica directa",
                    },
                },
            },
            "Guardrail": {
                "type": "object",
                "properties": {
                    "allowed": {"type": "boolean"},
                    "flagged_tokens": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "message": {"type": "string", "example": "OK"},
                },
            },
            "Sense": {
                "type": "object",
                "properties": {
                    "matches": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Match"},
                    },
                    "errors": {"type": "array", "items": {"type": "string"}},
                    "message": {"type": "string"},
                },
            },
            "PipelineResult": {
                "type": "object",
                "properties": {
                    "allowed": {"type": "boolean"},
                    "guardrail": {"$ref": "#/components/schemas/Guardrail"},
                    "sense": {"$ref": "#/components/schemas/Sense"},
                    "best_matches": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Match"},
                    },
                    "rendered_phrase": {
                        "type": "string",
                        "example": "niria: agua, líquido [NOM] (0.87)",
                    },
                },
            },
            "TranslateResponse": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "example": "agua"},
                    "tokens": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["agua"],
                    },
                    "result": {"$ref": "#/components/schemas/PipelineResult"},
                    "debug": {
                        "type": "object",
                        "description": "Solo presente si debug=true",
                        "properties": {
                            "regex": {"type": "string"},
                            "tokens": {"type": "array", "items": {"type": "string"}},
                            "matches": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Match"},
                            },
                            "errors": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "CommunitySummary": {
                "type": "object",
                "properties": {
                    "comunidad": {"type": "string", "example": "Arhuaco"},
                    "path": {"type": "string", "example": "/mnt/sayta_data/data/Grabaciones/Arhuaco"},
                    "total_grabaciones": {"type": "integer", "example": 5},
                    "total_archivos": {"type": "integer", "example": 42},
                },
            },
            "RecordingsRoot": {
                "type": "object",
                "properties": {
                    "base_path": {
                        "type": "string",
                        "example": "/mnt/sayta_data/data/Grabaciones",
                    },
                    "carpetas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Arhuaco", "Kogui"],
                    },
                    "total": {"type": "integer", "example": 2},
                    "resumen_comunidades": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/CommunitySummary"},
                    },
                },
            },
            "RecordingSession": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "example": "GRABACION 22 DE MARZO"},
                    "path": {
                        "type": "string",
                        "example": "/mnt/sayta_data/data/Grabaciones/Kogui/GRABACION 22 DE MARZO",
                    },
                    "fecha_texto": {"type": "string", "example": "22 de marzo", "nullable": True},
                    "fecha_iso": {"type": "string", "format": "date", "example": "2026-03-22", "nullable": True},
                },
            },
            "RecordingsByCommunity": {
                "type": "object",
                "properties": {
                    "comunidad": {"type": "string", "example": "Kogui"},
                    "path": {
                        "type": "string",
                        "example": "/mnt/sayta_data/data/Grabaciones/Kogui",
                    },
                    "grabaciones": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/RecordingSession"},
                    },
                    "total": {"type": "integer", "example": 2},
                },
            },
            "CommunityNotFound": {
                "type": "object",
                "properties": {
                    "error": {
                        "type": "string",
                        "example": "No se encontró la comunidad 'xyz'.",
                    },
                    "comunidades_disponibles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": ["Arhuaco", "Kogui"],
                    },
                },
            },
        }
    },
}
