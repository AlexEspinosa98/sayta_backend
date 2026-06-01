# Historias de Usuario — Ecosistema de Términos y Embeddings
## Proyecto Sayta — Traductor de Lenguas Indígenas

> **Base URL:** `http://localhost:8000`
> **Swagger UI:** `http://localhost:8000/api/terminos/docs/`

---

## Épica 1 — Gestión de Lenguas

### HU-01 — Registrar una lengua indígena

**Como** administrador, **quiero** registrar una nueva lengua indígena, **para** organizar sus términos y embeddings de forma independiente.

**Criterios de aceptación:**
- El campo `codigo` debe ser único (error 400 si se duplica).
- `activa=true` por defecto.
- Al listar, incluye total de términos activos y embedding activo.

```bash
# Crear lengua
curl -X POST http://localhost:8000/api/terminos/lenguas/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo": "ette",
    "nombre": "Ette Taara",
    "descripcion": "Lengua del pueblo Chimila, Sierra Nevada de Santa Marta",
    "activa": true
  }'

# Respuesta 201
{
  "id": 1,
  "codigo": "ette",
  "nombre": "Ette Taara",
  "descripcion": "Lengua del pueblo Chimila, Sierra Nevada de Santa Marta",
  "activa": true,
  "total_terminos": 0,
  "embedding_activo": null,
  "created_at": "2026-05-17T10:00:00Z",
  "updated_at": "2026-05-17T10:00:00Z"
}
```

---

### HU-02 — Listar y buscar lenguas

```bash
# Listar todas
curl http://localhost:8000/api/terminos/lenguas/

# Buscar por nombre o código
curl "http://localhost:8000/api/terminos/lenguas/?search=ette"

# Solo lenguas activas (ordenadas por nombre)
curl "http://localhost:8000/api/terminos/lenguas/?ordering=nombre"

# Respuesta
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "codigo": "ette",
      "nombre": "Ette Taara",
      "total_terminos": 3612,
      "embedding_activo": {
        "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
        "version": "20260517_100000",
        "num_terminos": 3612
      }
    }
  ]
}
```

---

### HU-03 — Actualizar / desactivar una lengua

```bash
# Actualización parcial
curl -X PATCH http://localhost:8000/api/terminos/lenguas/1/ \
  -H "Content-Type: application/json" \
  -d '{"activa": false}'

# Actualización completa
curl -X PUT http://localhost:8000/api/terminos/lenguas/1/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo": "ette",
    "nombre": "Ette Taara (Chimila)",
    "descripcion": "Lengua del pueblo Chimila",
    "activa": true
  }'

# Eliminar
curl -X DELETE http://localhost:8000/api/terminos/lenguas/1/
# Respuesta 204 No Content
```

---

## Épica 2 — Gestión de Términos en Español

### HU-04 — Crear y listar términos en español

```bash
# Crear
curl -X POST http://localhost:8000/api/terminos/terminos-es/ \
  -H "Content-Type: application/json" \
  -d '{"termino": "agua"}'

# Respuesta 201
{
  "id": 42,
  "termino": "agua",
  "traducciones_count": 0,
  "created_at": "2026-05-17T10:05:00Z",
  "updated_at": "2026-05-17T10:05:00Z"
}

# Listar con búsqueda
curl "http://localhost:8000/api/terminos/terminos-es/?search=agua&page_size=10"

# Respuesta
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{"id": 42, "termino": "agua", "traducciones_count": 2}]
}
```

---

## Épica 3 — Gestión de Términos en Lengua Indígena

### HU-05 — Crear un término en lengua indígena

**Como** administrador, **quiero** crear un término con su definición y metadatos, **para** construir el diccionario que alimentará el motor de traducción.

```bash
curl -X POST http://localhost:8000/api/terminos/terminos/ \
  -H "Content-Type: application/json" \
  -d '{
    "termino": "aabasu",
    "lengua": 1,
    "termino_es": 42,
    "definicion": "nombre de hombre",
    "pos": "NOM_PR",
    "sinonimos": [],
    "ejemplos": ["aabasu naka mutu"],
    "tipo_morfema": null,
    "activo": true
  }'

# Respuesta 201
{
  "id": 1001,
  "termino_es": 42,
  "termino_es_detail": {"id": 42, "termino": "nombre propio"},
  "lengua": 1,
  "lengua_detail": {"id": 1, "codigo": "ette", "nombre": "Ette Taara"},
  "termino": "aabasu",
  "definicion": "nombre de hombre",
  "pos": "NOM_PR",
  "sinonimos": [],
  "ejemplos": ["aabasu naka mutu"],
  "tipo_morfema": null,
  "activo": true,
  "created_at": "2026-05-17T10:10:00Z",
  "updated_at": "2026-05-17T10:10:00Z"
}
```

---

### HU-06 — Listar términos con paginación y filtros

**Como** administrador, **quiero** navegar el diccionario con filtros combinados, **para** encontrar y corregir términos rápidamente desde el frontend.

```bash
# Listar términos de la lengua 1, activos, página 2 de 50 por página
curl "http://localhost:8000/api/terminos/terminos/?lengua=1&activo=true&page=2&page_size=50"

# Buscar "agua" en termino y definicion de la lengua 1
curl "http://localhost:8000/api/terminos/terminos/?lengua=1&search=agua"

# Filtrar por parte del discurso (verbos)
curl "http://localhost:8000/api/terminos/terminos/?lengua=1&pos=VRB"

# Buscar por texto del equivalente en español
curl "http://localhost:8000/api/terminos/terminos/?termino_es_texto=nombre"

# Ver solo inactivos (desactivados con soft delete)
curl "http://localhost:8000/api/terminos/terminos/?activo=false"

# Ordenar por fecha de modificación (más reciente primero)
curl "http://localhost:8000/api/terminos/terminos/?ordering=-updated_at"

# Respuesta paginada
{
  "count": 3612,
  "next": "http://localhost:8000/api/terminos/terminos/?page=3&page_size=50",
  "previous": "http://localhost:8000/api/terminos/terminos/?page=1&page_size=50",
  "results": [
    {
      "id": 1001,
      "termino": "aabasu",
      "definicion": "nombre de hombre",
      "pos": "NOM_PR",
      "lengua_detail": {"id": 1, "codigo": "ette", "nombre": "Ette Taara"}
    }
  ]
}
```

---

### HU-07 — Corregir un término existente

```bash
# Actualización parcial (solo campos que cambian)
curl -X PATCH http://localhost:8000/api/terminos/terminos/1001/ \
  -H "Content-Type: application/json" \
  -d '{
    "definicion": "nombre propio masculino",
    "sinonimos": ["aaba"],
    "ejemplos": ["aabasu naka", "aabasu ichke"]
  }'

# Actualización completa
curl -X PUT http://localhost:8000/api/terminos/terminos/1001/ \
  -H "Content-Type: application/json" \
  -d '{
    "termino": "aabasu",
    "lengua": 1,
    "termino_es": 42,
    "definicion": "nombre propio masculino",
    "pos": "NOM_PR",
    "sinonimos": ["aaba"],
    "ejemplos": ["aabasu naka"],
    "tipo_morfema": null,
    "activo": true
  }'
```

---

### HU-08 — Soft delete y restaurar un término

**Como** administrador, **quiero** desactivar un término sin perderlo, **para** poder recuperarlo si fue un error.

```bash
# Desactivar (soft delete — NO elimina el registro)
curl -X DELETE http://localhost:8000/api/terminos/terminos/1001/
# Respuesta 204 No Content

# Verificar que quedó inactivo
curl "http://localhost:8000/api/terminos/terminos/1001/"
# → "activo": false

# Restaurar
curl -X POST http://localhost:8000/api/terminos/terminos/1001/restaurar/
# Respuesta 200 con el término reactivado
{
  "id": 1001,
  "termino": "aabasu",
  "activo": true,
  ...
}
```

---

### HU-09 — Carga masiva desde JSON

**Como** administrador, **quiero** cargar miles de términos de una sola vez desde un archivo JSON, **para** poblar el diccionario sin hacerlo uno a uno.

#### Opción A — JSON body

```bash
curl -X POST http://localhost:8000/api/terminos/terminos/carga-masiva/ \
  -H "Content-Type: application/json" \
  -d '{
    "lengua_id": 1,
    "modo": "upsert",
    "terminos": [
      {
        "termino": "aabasu",
        "definicion": "nombre de hombre",
        "pos": "NOM_PR",
        "sinonimos": [],
        "ejemplos": ["aabasu naka mutu"],
        "tipo_morfema": null,
        "termino_es": "nombre propio"
      },
      {
        "termino": "aani",
        "definicion": "agua",
        "pos": "NOM",
        "sinonimos": ["aayi"],
        "ejemplos": [],
        "tipo_morfema": null,
        "termino_es": "agua"
      },
      {
        "termino": "abichi",
        "definicion": "árbol grande",
        "pos": "NOM",
        "sinonimos": [],
        "ejemplos": [],
        "tipo_morfema": null
      }
    ]
  }'
```

#### Opción B — Archivo .json adjunto (multipart)

```bash
# El archivo terminos.json contiene SOLO el array de términos
# (sin los campos lengua_id / modo — esos van como campos del form)

curl -X POST http://localhost:8000/api/terminos/terminos/carga-masiva/ \
  -F "archivo=@/ruta/a/terminos.json;type=application/json" \
  -F "lengua_id=1" \
  -F "modo=upsert"
```

**Estructura del archivo `terminos.json`:**
```json
[
  {
    "termino": "aabasu",
    "definicion": "nombre de hombre",
    "pos": "NOM_PR",
    "sinonimos": [],
    "ejemplos": ["aabasu naka mutu"],
    "tipo_morfema": null,
    "termino_es": "nombre propio"
  },
  {
    "termino": "aani",
    "definicion": "agua",
    "pos": "NOM",
    "sinonimos": ["aayi"],
    "ejemplos": [],
    "tipo_morfema": null,
    "termino_es": "agua"
  }
]
```

**Modos disponibles:**

| Modo | Si el término ya existe | Si el término es nuevo |
|---|---|---|
| `upsert` (default) | Actualiza si cambió algo | Crea |
| `crear` | Salta (sin_cambios) | Crea |
| `actualizar` | Actualiza si cambió algo | Salta (sin_cambios) |

**Respuesta 200 (sin errores) / 207 (con errores parciales):**
```json
{
  "total": 3612,
  "creados": 3200,
  "actualizados": 350,
  "sin_cambios": 52,
  "errores": 10,
  "detalle_errores": [
    {
      "indice": 5,
      "termino": "xxx??",
      "error": "El campo termino es obligatorio."
    },
    {
      "indice": 88,
      "termino": "aani",
      "error": "Ya existe un término \"aani\" para esta lengua."
    }
  ]
}
```

---

## Épica 4 — Generación y Gestión de Embeddings

### HU-10 — Generar embeddings para una lengua (asíncrono)

**Como** administrador, **quiero** generar nuevos embeddings cuando actualice el diccionario, **para** mantener el motor de búsqueda semántica actualizado.

```bash
curl -X POST http://localhost:8000/api/terminos/embeddings/generar/ \
  -H "Content-Type: application/json" \
  -d '{
    "lengua_id": 1,
    "model_name": "intfloat/multilingual-e5-base"
  }'

# Respuesta 202 — retorna INMEDIATAMENTE sin bloquear
{
  "message": "Generación iniciada en segundo plano.",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "embedding_version_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c"
}

# Si ya hay una generación en curso para esta lengua → 409
{
  "error": "Ya hay una generación en curso para esta lengua.",
  "task_id": "anterior-task-id",
  "status": "generating"
}
```

---

### HU-11 — Monitorear el estado de la generación (polling)

**Como** administrador, **quiero** consultar el progreso de la generación, **para** saber cuándo está lista para activar.

```bash
curl http://localhost:8000/api/terminos/embeddings/estado/550e8400-e29b-41d4-a716-446655440000/

# Mientras genera → status: "generating"
{
  "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "lengua": 1,
  "lengua_detail": {"id": 1, "codigo": "ette", "nombre": "Ette Taara"},
  "version": "20260517_100000",
  "model_name": "intfloat/multilingual-e5-base",
  "status": "generating",
  "status_display": "Generando",
  "is_active": false,
  "num_terminos": 0,
  "error_message": "",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-05-17T10:00:00Z",
  "completed_at": null
}

# Cuando termina → status: "ready"
{
  "status": "ready",
  "status_display": "Listo",
  "num_terminos": 3612,
  "completed_at": "2026-05-17T10:08:32Z"
}

# Si falló → status: "failed"
{
  "status": "failed",
  "status_display": "Fallido",
  "error_message": "No hay términos activos para esta lengua"
}
```

---

### HU-12 — Listar versiones de embeddings

**Como** administrador, **quiero** ver el historial de versiones disponibles, **para** comparar y elegir cuál activar.

```bash
# Todas las versiones de la lengua 1
curl "http://localhost:8000/api/terminos/embeddings/?lengua=1"

# Solo las versiones listas para activar
curl "http://localhost:8000/api/terminos/embeddings/?lengua=1&status=ready"

# Ver la versión actualmente activa
curl "http://localhost:8000/api/terminos/embeddings/?lengua=1&is_active=true"

# Respuesta
{
  "count": 3,
  "results": [
    {
      "id": "7f3e4c2a-...",
      "version": "20260517_100000",
      "status": "ready",
      "is_active": false,
      "num_terminos": 3612,
      "created_at": "2026-05-17T10:00:00Z",
      "completed_at": "2026-05-17T10:08:32Z"
    },
    {
      "id": "3a1b2c4d-...",
      "version": "20260510_090000",
      "status": "active",
      "is_active": true,
      "num_terminos": 3500,
      "created_at": "2026-05-10T09:00:00Z",
      "completed_at": "2026-05-10T09:07:15Z"
    }
  ]
}
```

---

### HU-13 — Activar una versión de embedding

**Como** administrador, **quiero** decidir cuál versión de embeddings usa el motor de traducción, **para** tener control total sobre cuándo se actualiza la búsqueda semántica.

```bash
curl -X POST http://localhost:8000/api/terminos/embeddings/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c/activar/

# Respuesta 200 — motor recargado en caliente
{
  "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "version": "20260517_100000",
  "status": "active",
  "is_active": true,
  "num_terminos": 3612,
  "completed_at": "2026-05-17T10:08:32Z"
}

# Si el estado no permite activar → 400
{
  "error": "No se puede activar un embedding con estado \"generating\". Debe estar en estado \"ready\" o \"active\"."
}
```

---

## Flujo completo paso a paso

```bash
# 1. Crear la lengua
curl -X POST http://localhost:8000/api/terminos/lenguas/ \
  -H "Content-Type: application/json" \
  -d '{"codigo": "ette", "nombre": "Ette Taara"}'
# → id: 1

# 2. Cargar el diccionario completo
curl -X POST http://localhost:8000/api/terminos/terminos/carga-masiva/ \
  -F "archivo=@diccionario_ette.json;type=application/json" \
  -F "lengua_id=1" \
  -F "modo=upsert"
# → {"creados": 3612, "errores": 0, ...}

# 3. Corregir términos individuales si es necesario
curl -X PATCH http://localhost:8000/api/terminos/terminos/1001/ \
  -H "Content-Type: application/json" \
  -d '{"definicion": "nombre propio masculino"}'

# 4. Generar embeddings
curl -X POST http://localhost:8000/api/terminos/embeddings/generar/ \
  -H "Content-Type: application/json" \
  -d '{"lengua_id": 1}'
# → task_id: "550e8400-..."

# 5. Hacer polling hasta status=ready (frontend puede hacerlo cada 5s)
curl http://localhost:8000/api/terminos/embeddings/estado/550e8400-.../
# → {"status": "ready", "num_terminos": 3612, "id": "7f3e4c2a-..."}

# 6. Activar la nueva versión
curl -X POST http://localhost:8000/api/terminos/embeddings/7f3e4c2a-.../activar/
# → {"status": "active", "is_active": true}
# ✓ Motor de búsqueda recargado automáticamente
```

---

---

## Épica 5 — Traducción Texto a Texto

### HU-14 — Traducir texto con análisis multi-estrategia y conclusión

**Como** usuario del traductor, **quiero** enviar un texto (palabra suelta o frase de varios términos) en español o en una lengua indígena, **para** obtener una conclusión clara con la traducción más probable y tres alternativas ordenadas por probabilidad con su definición.

**Criterios de aceptación:**
- El cliente envía `texto`, `lengua_id` y `direccion` (`es_a_lengua` o `lengua_a_es`).
- Si la lengua no existe → 404.
- Si la lengua no tiene embedding activo → 422 con mensaje de ayuda.
- El pipeline analiza el texto en tres niveles: frase completa, n-gramas y tokens individuales.
- Los resultados de los tres niveles se fusionan por término; para duplicados se conserva el mayor score.
- La respuesta incluye `conclusion` con el resultado de mayor probabilidad.
- Cada resultado en `resultados` incluye `termino` (lengua indígena), `termino_es` (español), `definicion`, `score`, `probabilidad` (los 3 suman 100 %), `mejor_coincidencia` y `coincidencia` (qué sub-consulta lo encontró).
- Se indica qué versión de embedding se usó (id, versión, modelo, número de términos).

**Endpoint:** `POST /api/traduccion/traducir/`

---

#### Caso 1 — Palabra simple, Español → Arhuaco

```bash
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{
    "texto": "jaguar",
    "lengua_id": 1,
    "direccion": "es_a_lengua"
  }'

# Respuesta 200
{
  "texto_entrada": "jaguar",
  "lengua": { "id": 1, "codigo": "iku", "nombre": "Arhuaco" },
  "embedding": {
    "version_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
    "version": "20260527_100000",
    "modelo": "intfloat/multilingual-e5-base",
    "num_terminos": 197
  },
  "direccion": "es→iku",
  "conclusion": {
    "termino": "Tigri",
    "termino_es": "jaguar",
    "definicion": "Jaguar (Panthera onca). Felino más grande de América.",
    "probabilidad": 52.4
  },
  "resultados": [
    {
      "termino": "Tigri",
      "termino_es": "jaguar",
      "definicion": "Jaguar (Panthera onca). Felino más grande de América.",
      "score": 0.9410,
      "probabilidad": 52.4,
      "mejor_coincidencia": true,
      "coincidencia": "jaguar"
    },
    {
      "termino": "Munkwu",
      "termino_es": "araña",
      "definicion": "Araña. Arácnido de la Sierra Nevada.",
      "score": 0.5120,
      "probabilidad": 28.5,
      "mejor_coincidencia": false,
      "coincidencia": "jaguar"
    },
    {
      "termino": "Zeyku",
      "termino_es": "escorpión",
      "definicion": "Escorpión. Arácnido venenoso.",
      "score": 0.3410,
      "probabilidad": 19.0,
      "mejor_coincidencia": false,
      "coincidencia": "jaguar"
    }
  ]
}
```

---

#### Caso 2 — Frase compuesta, Arhuaco → Español

El pipeline divide la frase en niveles: frase completa, bi/tri-gramas y tokens. Los resultados de todos los niveles se fusionan y se ordenan por probabilidad.

```bash
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{
    "texto": "Du zari bunsi chano",
    "lengua_id": 1,
    "direccion": "lengua_a_es"
  }'

# Respuesta 200
{
  "texto_entrada": "Du zari bunsi chano",
  "lengua": { "id": 1, "codigo": "iku", "nombre": "Arhuaco" },
  "embedding": { ... },
  "direccion": "iku→es",
  "conclusion": {
    "termino": "Du zari bunsi chano",
    "termino_es": "buenos días",
    "definicion": "Saludo de la mañana en lengua ikʉn.",
    "probabilidad": 46.2
  },
  "resultados": [
    {
      "termino": "Du zari bunsi chano",
      "termino_es": "buenos días",
      "definicion": "Saludo de la mañana en lengua ikʉn.",
      "score": 0.9801,
      "probabilidad": 46.2,
      "mejor_coincidencia": true,
      "coincidencia": "Du zari bunsi chano"
    },
    {
      "termino": "Du zari ɉwi nayo",
      "termino_es": "buenas tardes",
      "definicion": "Saludo de la tarde en lengua ikʉn.",
      "score": 0.8740,
      "probabilidad": 41.2,
      "mejor_coincidencia": false,
      "coincidencia": "Du zari"
    },
    {
      "termino": "Bunachʉn",
      "termino_es": "español",
      "definicion": "Nombre del español o castellano en lengua ikʉn.",
      "score": 0.2680,
      "probabilidad": 12.6,
      "mejor_coincidencia": false,
      "coincidencia": "chano"
    }
  ]
}
```

> El campo `coincidencia` muestra qué sub-consulta encontró cada resultado:
> - `"Du zari bunsi chano"` → lo encontró la búsqueda de frase completa (nivel 1)
> - `"Du zari"` → lo encontró un bigrama (nivel 2)
> - `"chano"` → lo encontró un token individual (nivel 3)

---

#### Caso 3 — Lengua sin embedding activo

```bash
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{"texto": "montaña", "lengua_id": 2, "direccion": "es_a_lengua"}'

# Respuesta 422
{
  "error": "La lengua \"Kogui\" no tiene un embedding activo. Genera uno con POST /api/terminos/embeddings/generar/ y actívalo con POST /api/terminos/embeddings/{id}/activar/."
}
```

---

#### Caso 4 — Lengua inexistente

```bash
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{"texto": "sol", "lengua_id": 99, "direccion": "es_a_lengua"}'

# Respuesta 404
{ "error": "Lengua con id=99 no existe." }
```

---

#### Caso 5 — Body inválido

```bash
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{"texto": "agua", "lengua_id": 1}'

# Respuesta 400
{ "direccion": ["Este campo es requerido."] }
```

---

### Campos del request

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `texto` | string | Sí | Texto a traducir (palabra o frase) |
| `lengua_id` | integer | Sí | ID de la lengua indígena |
| `direccion` | string | Sí | `"es_a_lengua"` o `"lengua_a_es"` |

---

### Campos de la respuesta

| Campo | Tipo | Descripción |
|---|---|---|
| `texto_entrada` | string | Texto recibido |
| `lengua.id` | integer | ID de la lengua |
| `lengua.codigo` | string | Código corto (ej. `iku`) |
| `lengua.nombre` | string | Nombre completo (ej. `Arhuaco`) |
| `embedding.version_id` | UUID | ID de la versión de embedding usada |
| `embedding.version` | string | Timestamp de generación |
| `embedding.modelo` | string | Modelo utilizado |
| `embedding.num_terminos` | integer | Términos en el índice |
| `direccion` | string | Dirección formateada (ej. `es→iku`) |
| `conclusion.termino` | string | Término con mayor probabilidad |
| `conclusion.termino_es` | string | Equivalente en español |
| `conclusion.definicion` | string | Definición en español |
| `conclusion.probabilidad` | float | % de probabilidad sobre los 3 resultados |
| `resultados[].termino` | string | Término en la lengua indígena |
| `resultados[].termino_es` | string | Equivalente en español |
| `resultados[].definicion` | string | Definición en español |
| `resultados[].score` | float | Similitud coseno cruda (0–1) |
| `resultados[].probabilidad` | float | % relativo (los 3 suman 100 %) |
| `resultados[].mejor_coincidencia` | bool | `true` solo en el resultado #1 |
| `resultados[].coincidencia` | string | Sub-consulta que produjo este resultado |

---

### Cómo funciona el pipeline internamente

Para una entrada de `N` palabras el sistema ejecuta hasta `1 + bigramas + trigramas + tokens` búsquedas semánticas en el índice FAISS:

```
Entrada: "Du zari bunsi chano"   (4 tokens)

Nivel 1 — frase completa  (peso 1.00)
  → "Du zari bunsi chano"

Nivel 2 — bi/tri-gramas   (peso 0.92)
  → "Du zari" · "zari bunsi" · "bunsi chano"
  → "Du zari bunsi" · "zari bunsi chano"

Nivel 3 — tokens solos    (peso 0.80, solo si len > 2)
  → "zari" · "bunsi" · "chano"

Fusión: por término, conserva el mayor score ajustado
Filtro: descarta scores < 0.30
Top 3: ordena descendente y toma los primeros 3
Probabilidad: score_i / suma_total × 100
Conclusión: el resultado #1 (mayor probabilidad)
```

---

### Flujo completo

```bash
# Prerrequisito: embedding activo (Épica 4, HU-10 → HU-13)
curl "http://localhost:8000/api/terminos/embeddings/?lengua=1&is_active=true"

# Traducir español → arhuaco
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{"texto": "jaguar", "lengua_id": 1, "direccion": "es_a_lengua"}'

# Traducir frase arhuaca → español
curl -X POST http://localhost:8000/api/traduccion/traducir/ \
  -H "Content-Type: application/json" \
  -d '{"texto": "Du zari bunsi chano", "lengua_id": 1, "direccion": "lengua_a_es"}'
```

---

## Swagger UI

La documentación interactiva completa está disponible en:

```
http://localhost:8000/api/docs/
```

Schema OpenAPI JSON:
```
http://localhost:8000/api/schema/
```

---

---

## Épica 6 — Entrenamiento de Modelos ASR (Audio → Texto)

> **Base URL entrenamiento:** `http://localhost:8000/api/entrenamiento/`
>
> Esta épica cubre el ciclo completo de fine-tuning de modelos de reconocimiento de voz (ASR)
> para las lenguas indígenas del proyecto. El flujo es:
> **descargar modelo → explorar datos etiquetados → seleccionar carpetas → entrenar → monitorear → activar → usar en transcripción.**

---

### HU-15 — Consultar las lenguas del sistema y su estado de modelos ASR

**Como** investigador, **quiero** ver las lenguas registradas en la base de datos junto con su estado de modelos ASR, **para** saber qué `lengua_id` usar al lanzar un entrenamiento y si esa lengua ya tiene un modelo activo.

**Criterios de aceptación:**
- Se listan solo las lenguas con `activa: true`.
- Por cada lengua se indica si tiene un modelo ASR activo (`tiene_modelo_activo`), los detalles del experimento activo y qué modelos descargados están disponibles para entrenar.
- El campo `id` de cada lengua es el `lengua_id` que se pasa a `POST /api/entrenamiento/entrenar/`.
- Si no hay ningún modelo descargado, `modelos_disponibles_para_entrenar` es una lista vacía.

```bash
curl http://localhost:8000/api/entrenamiento/lenguas/

# Respuesta 200
{
  "total": 2,
  "lenguas": [
    {
      "id": 1,
      "codigo": "iku",
      "nombre": "Arhuaco",
      "tiene_modelo_activo": true,
      "modelo_activo": {
        "experimento_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
        "nombre": "whisper-small-iku-v2",
        "modelo_hf": "openai/whisper-small",
        "metricas": {
          "eval_wer": 0.1820,
          "eval_cer": 0.0541,
          "train_loss": 0.2134
        },
        "completed_at": "2026-06-01T11:34:02Z"
      },
      "ultimo_experimento": null,
      "modelos_descargados": 2,
      "modelos_disponibles_para_entrenar": [
        {"id": 1, "nombre_hf": "openai/whisper-small", "tipo": "whisper"},
        {"id": 2, "nombre_hf": "facebook/wav2vec2-large-xlsr-53", "tipo": "wav2vec2"}
      ]
    },
    {
      "id": 2,
      "codigo": "kogui",
      "nombre": "Kogui",
      "tiene_modelo_activo": false,
      "modelo_activo": null,
      "ultimo_experimento": {
        "id": "3a1b2c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
        "nombre": "whisper-tiny-kogui-v1",
        "estado": "fallido",
        "created_at": "2026-05-30T08:00:00Z"
      },
      "modelos_descargados": 2,
      "modelos_disponibles_para_entrenar": [
        {"id": 1, "nombre_hf": "openai/whisper-small", "tipo": "whisper"},
        {"id": 2, "nombre_hf": "facebook/wav2vec2-large-xlsr-53", "tipo": "wav2vec2"}
      ]
    }
  ]
}
```

**Notas para el frontend:**
- **Este es el primer endpoint a llamar** antes de mostrar el formulario de entrenamiento — da el `lengua_id` correcto y el estado actual de cada lengua.
- Mostrar badge "Modelo activo ✓" en verde si `tiene_modelo_activo: true`.
- Si `tiene_modelo_activo: false` y `ultimo_experimento.estado == "fallido"`, mostrar advertencia en rojo.
- Si `modelos_disponibles_para_entrenar` está vacío, deshabilitar el botón de entrenar con tooltip "Descarga primero un modelo base".

---

### HU-15b — Ver resumen del dataset disponible para entrenamiento

**Como** investigador, **quiero** ver cuántos audios etiquetados hay por comunidad y jornada, **para** saber si hay suficientes datos antes de lanzar un entrenamiento.

**Criterios de aceptación:**
- El frontend muestra todas las comunidades disponibles en disco (`Grabaciones/`).
- Por cada comunidad se ve: total de audios, cuántos están etiquetados, cuántos faltan y el porcentaje completado.
- El campo `apto_para_entrenamiento` indica si hay mínimo 5 muestras etiquetadas.
- Si el directorio de grabaciones no existe → se indica con `existe: false`.

```bash
curl http://localhost:8000/api/entrenamiento/dataset/

# Respuesta 200
{
  "base_path": "/mnt/sayta_data/data/Grabaciones",
  "existe": true,
  "total_comunidades": 2,
  "comunidades": [
    {
      "comunidad": "arhuaco",
      "total_jornadas": 4,
      "total_audios": 87,
      "etiquetados": 62,
      "sin_etiquetar": 25,
      "porcentaje_completado": 71.3,
      "apto_para_entrenamiento": true
    },
    {
      "comunidad": "kogui",
      "total_jornadas": 2,
      "total_audios": 34,
      "etiquetados": 3,
      "sin_etiquetar": 31,
      "porcentaje_completado": 8.8,
      "apto_para_entrenamiento": false
    }
  ]
}
```

**Notas para el frontend:**
- Renderizar cada comunidad como una tarjeta con una barra de progreso.
- Mostrar `apto_para_entrenamiento: false` en color rojo/naranja como advertencia.
- El botón "Seleccionar para entrenar" solo se habilita si `apto_para_entrenamiento: true`.

---

### HU-15c — Ver lista completa de todas las jornadas disponibles (selección granular)

**Como** investigador, **quiero** ver en una sola llamada todas las jornadas de todas las comunidades con sus conteos de audios etiquetados, **para** poder marcar individualmente cuáles jornadas incluir en el entrenamiento usando checkboxes.

**Criterios de aceptación:**
- La respuesta es una lista plana (sin anidamiento) de todas las jornadas de todas las comunidades.
- Cada ítem incluye: `comunidad`, `jornada`, `total_audios`, `etiquetados`, `sin_etiquetar`, `porcentaje` y `apta` (tiene al menos 1 audio etiquetado).
- El frontend puede filtrar por `apta: true` para mostrar solo las usables.
- Si el directorio de grabaciones no existe → `existe: false` con lista vacía.

```bash
curl http://localhost:8000/api/entrenamiento/dataset/sesiones/

# Respuesta 200
{
  "existe": true,
  "total_sesiones": 6,
  "total_etiquetados": 65,
  "sesiones": [
    {
      "comunidad": "arhuaco",
      "jornada": "grabacion_15_03_26_fauna",
      "total_audios": 23,
      "etiquetados": 23,
      "sin_etiquetar": 0,
      "porcentaje": 100.0,
      "apta": true
    },
    {
      "comunidad": "arhuaco",
      "jornada": "grabacion_22_03_26_territorio",
      "total_audios": 31,
      "etiquetados": 21,
      "sin_etiquetar": 10,
      "porcentaje": 67.7,
      "apta": true
    },
    {
      "comunidad": "arhuaco",
      "jornada": "grabacion_05_04_26_cosmogonia",
      "total_audios": 18,
      "etiquetados": 12,
      "sin_etiquetar": 6,
      "porcentaje": 66.7,
      "apta": true
    },
    {
      "comunidad": "arhuaco",
      "jornada": "grabacion_20_04_26_saludos",
      "total_audios": 15,
      "etiquetados": 6,
      "sin_etiquetar": 9,
      "porcentaje": 40.0,
      "apta": true
    },
    {
      "comunidad": "kogui",
      "jornada": "grabacion_10_03_26_rituales",
      "total_audios": 12,
      "etiquetados": 3,
      "sin_etiquetar": 9,
      "porcentaje": 25.0,
      "apta": true
    },
    {
      "comunidad": "kogui",
      "jornada": "grabacion_01_05_26_naturaleza",
      "total_audios": 8,
      "etiquetados": 0,
      "sin_etiquetar": 8,
      "porcentaje": 0.0,
      "apta": false
    }
  ]
}
```

**Notas para el frontend:**
- Usar esta respuesta para renderizar una tabla o lista con **checkboxes individuales** por jornada.
- Agrupar visualmente por `comunidad` con un encabezado de sección y un "seleccionar todos" por comunidad.
- Las sesiones con `apta: false` deben mostrarse en gris y con el checkbox deshabilitado.
- Al marcar/desmarcar checkboxes, actualizar en tiempo real el contador total de muestras seleccionadas (sumar `etiquetados` de los items marcados).
- Al enviar, mapear los checkboxes marcados al campo `sesiones` del `POST /api/entrenamiento/entrenar/`:
  ```json
  "sesiones": [
    {"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"},
    {"comunidad": "arhuaco", "jornada": "grabacion_22_03_26_territorio"}
  ]
  ```

---

### HU-16 — Explorar jornadas de una comunidad antes de entrenar

**Como** investigador, **quiero** ver el detalle de cuántos audios etiquetados hay jornada por jornada dentro de una comunidad, **para** identificar qué sesiones de grabación contribuyen más datos al entrenamiento.

**Criterios de aceptación:**
- El frontend puede expandir una comunidad para ver su desglose por jornada.
- Cada jornada muestra: nombre, total de audios, etiquetados y porcentaje.
- Si la comunidad no existe → 404.

```bash
curl http://localhost:8000/api/entrenamiento/dataset/arhuaco/

# Respuesta 200
{
  "comunidad": "arhuaco",
  "total_audios": 87,
  "etiquetados": 62,
  "apto_para_entrenamiento": true,
  "jornadas": [
    {
      "jornada": "grabacion_15_03_26_fauna",
      "total_audios": 23,
      "etiquetados": 23,
      "porcentaje": 100.0
    },
    {
      "jornada": "grabacion_22_03_26_territorio",
      "total_audios": 31,
      "etiquetados": 21,
      "porcentaje": 67.7
    },
    {
      "jornada": "grabacion_05_04_26_cosmogonia",
      "total_audios": 18,
      "etiquetados": 12,
      "porcentaje": 66.7
    },
    {
      "jornada": "grabacion_20_04_26_saludos",
      "total_audios": 15,
      "etiquetados": 6,
      "porcentaje": 40.0
    }
  ]
}

# Comunidad inexistente → 404
{ "error": "Comunidad 'wiwa' no encontrada." }
```

**Notas para el frontend:**
- Mostrar un acordeón o tabla desplegable por jornada.
- Las jornadas con 100% etiquetadas se marcan con ícono de verificado.
- Esta vista ayuda al investigador a decidir si debe etiquetar más antes de entrenar.

---

### HU-17 — Ver catálogo de modelos de audio disponibles en HuggingFace

**Como** investigador, **quiero** ver los modelos ASR recomendados para fine-tuning en lenguas indígenas, **para** elegir el más adecuado según el hardware disponible y la cantidad de datos.

**Criterios de aceptación:**
- Se muestran 5 modelos curados (Whisper tiny, small, medium; Wav2Vec2 base, XLSR-53).
- Por cada modelo se indica: nombre HF, tipo (whisper/wav2vec2), descripción, tamaño aproximado, si está descargado y si está recomendado.
- Los modelos ya descargados se marcan visualmente diferente.

```bash
curl http://localhost:8000/api/entrenamiento/modelos-disponibles/

# Respuesta 200
{
  "total": 5,
  "modelos": [
    {
      "nombre_hf": "openai/whisper-small",
      "tipo": "whisper",
      "descripcion": "Whisper Small — 244M parámetros. Multilingüe, excelente para fine-tuning en lenguas indígenas. Balance ideal rendimiento/tamaño. Recomendado.",
      "tamaño_aprox": "461 MB",
      "parametros": "244M",
      "recomendado": true,
      "gpu_requerida": false,
      "descargado": false,
      "id_bd": null
    },
    {
      "nombre_hf": "openai/whisper-tiny",
      "tipo": "whisper",
      "descripcion": "Whisper Tiny — 39M parámetros. El más ligero; adecuado para hardware sin GPU o pruebas rápidas con pocos datos.",
      "tamaño_aprox": "151 MB",
      "parametros": "39M",
      "recomendado": false,
      "gpu_requerida": false,
      "descargado": true,
      "id_bd": 1
    },
    {
      "nombre_hf": "openai/whisper-medium",
      "tipo": "whisper",
      "descripcion": "Whisper Medium — 769M parámetros. Mayor precisión, requiere GPU con 8GB+.",
      "tamaño_aprox": "1.5 GB",
      "parametros": "769M",
      "recomendado": false,
      "gpu_requerida": true,
      "descargado": false,
      "id_bd": null
    },
    {
      "nombre_hf": "facebook/wav2vec2-large-xlsr-53",
      "tipo": "wav2vec2",
      "descripcion": "Wav2Vec2 XLSR-53 — 315M parámetros. Pre-entrenado en 53 idiomas con CTC. Muy adecuado para fine-tuning con pocos recursos. Recomendado.",
      "tamaño_aprox": "1.2 GB",
      "parametros": "315M",
      "recomendado": true,
      "gpu_requerida": false,
      "descargado": false,
      "id_bd": null
    },
    {
      "nombre_hf": "facebook/wav2vec2-base",
      "tipo": "wav2vec2",
      "descripcion": "Wav2Vec2 Base — 95M parámetros. Más pequeño, solo inglés pre-entrenado. Útil para pruebas de pipeline o datasets muy pequeños.",
      "tamaño_aprox": "370 MB",
      "parametros": "95M",
      "recomendado": false,
      "gpu_requerida": false,
      "descargado": false,
      "id_bd": null
    }
  ]
}
```

**Notas para el frontend:**
- Mostrar badge "Recomendado" en verde para `recomendado: true`.
- Mostrar badge "Descargado ✓" para `descargado: true` y deshabilitar el botón de descargar.
- Mostrar badge "GPU requerida" en amarillo para `gpu_requerida: true`.
- El botón "Descargar" llama a HU-18.

---

### HU-18 — Descargar un modelo desde HuggingFace Hub

**Como** investigador, **quiero** descargar un modelo al servidor local, **para** usarlo en entrenamiento sin depender de conexión a internet durante el fine-tuning.

**Criterios de aceptación:**
- La descarga es sincrónica (puede tardar varios minutos).
- Si el modelo ya está descargado → 200 con mensaje indicándolo (idempotente).
- Si la descarga falla → 500 con el mensaje de error de HuggingFace.
- El modelo queda registrado en BD con `descargado: true`.

```bash
# Descargar Whisper Small
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_hf": "openai/whisper-small",
    "tipo": "whisper",
    "descripcion": "Whisper Small para fine-tuning en IKU y KOGUI"
  }'

# Respuesta 201 — primera descarga
{
  "mensaje": "openai/whisper-small descargado correctamente.",
  "modelo": {
    "id": 1,
    "nombre_hf": "openai/whisper-small",
    "tipo": "whisper",
    "tipo_display": "Whisper (Seq2Seq)",
    "descripcion": "Whisper Small para fine-tuning en IKU y KOGUI",
    "ruta_local": "/app/audio_models/openai__whisper-small",
    "descargado": true,
    "created_at": "2026-06-01T10:00:00Z"
  }
}

# Respuesta 200 — modelo ya descargado (idempotente)
{
  "mensaje": "El modelo ya está descargado.",
  "modelo": { ... }
}

# Error de descarga → 500
{
  "error": "Repository 'openai/whisper-xxl' not found on HuggingFace Hub."
}
```

```bash
# Descargar Wav2Vec2 XLSR-53
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_hf": "facebook/wav2vec2-large-xlsr-53",
    "tipo": "wav2vec2"
  }'
```

**Notas para el frontend:**
- Mostrar un spinner/indicador de progreso mientras se descarga (la llamada es lenta).
- Después de 201, refrescar el catálogo (HU-17) para actualizar el badge "Descargado ✓".

---

### HU-19 — Listar modelos ASR descargados localmente

**Como** investigador, **quiero** ver qué modelos están disponibles en el servidor local, **para** elegir cuál usar al lanzar un entrenamiento.

```bash
curl http://localhost:8000/api/entrenamiento/modelos/

# Respuesta 200
{
  "total": 2,
  "modelos": [
    {
      "id": 1,
      "nombre_hf": "openai/whisper-small",
      "tipo": "whisper",
      "tipo_display": "Whisper (Seq2Seq)",
      "descripcion": "Whisper Small para fine-tuning en IKU y KOGUI",
      "ruta_local": "/app/audio_models/openai__whisper-small",
      "descargado": true,
      "created_at": "2026-06-01T10:00:00Z"
    },
    {
      "id": 2,
      "nombre_hf": "facebook/wav2vec2-large-xlsr-53",
      "tipo": "wav2vec2",
      "tipo_display": "Wav2Vec2 (CTC)",
      "descripcion": "",
      "ruta_local": "/app/audio_models/facebook__wav2vec2-large-xlsr-53",
      "descargado": true,
      "created_at": "2026-06-01T10:15:00Z"
    }
  ]
}
```

---

### HU-20 — Lanzar fine-tuning con selección granular de datos

**Como** investigador, **quiero** elegir exactamente qué jornadas de qué comunidades incluir en el entrenamiento (o usar todos los datos disponibles de una vez), especificar el modelo base y configurar hiperparámetros, **para** iniciar un entrenamiento controlado y reproducible para una lengua específica.

**Criterios de aceptación:**
- Campos obligatorios: `nombre`, `lengua_id` (de `GET /api/entrenamiento/lenguas/`), `modelo_audio_id` (de `GET /api/entrenamiento/modelos/`).
- **Exactamente uno** de los tres modos de selección de datos debe incluirse:
  - `"todos": true` — usa todos los audios etiquetados del sistema.
  - `"sesiones": [{comunidad, jornada}, ...]` — jornadas individuales seleccionadas.
  - `"comunidades": ["arhuaco", ...]` — todas las jornadas de las comunidades listadas.
- Si ningún modo está presente → 400 con mensaje explicativo.
- Si el total de muestras < 5 → 422 con cuántas se encontraron y el modo usado.
- Si el modelo no está descargado → 422 con instrucción.
- Si ya hay un entrenamiento en curso para esa lengua y modelo → 409.
- El entrenamiento corre en segundo plano → retorna 202 inmediatamente con `experimento_id`.
- El sistema registra automáticamente el experimento en MLflow como `sayta-asr-{lengua.codigo}`.

---

**Modo 1 — Todos los audios del sistema**

```bash
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "whisper-small-iku-full-v1",
    "lengua_id": 1,
    "modelo_audio_id": 1,
    "todos": true,
    "config": {
      "num_train_epochs": 20,
      "learning_rate": 1e-5,
      "use_peft": false
    }
  }'
```

---

**Modo 2 — Jornadas específicas (granular)**

Usar los valores de `comunidad` y `jornada` que devuelve `GET /api/entrenamiento/dataset/sesiones/`.

```bash
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "whisper-small-iku-fauna-v1",
    "lengua_id": 1,
    "modelo_audio_id": 1,
    "sesiones": [
      {"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"},
      {"comunidad": "arhuaco", "jornada": "grabacion_22_03_26_territorio"},
      {"comunidad": "kogui",   "jornada": "grabacion_10_03_26_rituales"}
    ],
    "config": {
      "num_train_epochs": 15,
      "per_device_train_batch_size": 4,
      "learning_rate": 1e-5
    }
  }'
```

---

**Modo 3 — Comunidades completas**

```bash
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "wav2vec2-xlsr-bilingue-v1",
    "lengua_id": 1,
    "modelo_audio_id": 2,
    "comunidades": ["arhuaco", "kogui"],
    "config": {
      "num_train_epochs": 30,
      "learning_rate": 1e-4,
      "use_peft": true,
      "peft_r": 16,
      "peft_alpha": 32
    }
  }'
```

---

**Respuestas comunes a los tres modos**

```json
// 202 — Entrenamiento iniciado
{
  "mensaje": "Entrenamiento iniciado.",
  "experimento_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "num_muestras": 62,
  "estado_url": "/api/entrenamiento/experimentos/7f3e4c2a-.../estado/"
}

// 422 — Datos insuficientes
{
  "error": "Se necesitan al menos 5 muestras etiquetadas. Solo se encontraron 3. Etiqueta más audios antes de entrenar.",
  "muestras_encontradas": 3,
  "seleccion": {"modo": "sesiones", "sesiones": [...]}
}

// 422 — Modelo no descargado
{
  "error": "El modelo \"openai/whisper-medium\" no está descargado. Descárgalo primero con POST /api/entrenamiento/modelos/descargar/"
}

// 409 — Ya hay entrenamiento en curso
{
  "error": "Ya hay un entrenamiento en curso para esta lengua y modelo."
}

// 400 — Ningún modo especificado
{
  "non_field_errors": ["Debes especificar al menos uno: \"todos\": true, \"sesiones\": [...], o \"comunidades\": [...]"]
}
```

---

**Tabla de hiperparámetros disponibles en `config`**

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `num_train_epochs` | int | 20 | Épocas de entrenamiento |
| `per_device_train_batch_size` | int | 4 | Batch por GPU/CPU |
| `per_device_eval_batch_size` | int | 4 | Batch de evaluación |
| `gradient_accumulation_steps` | int | 2 | Pasos antes de actualizar gradientes |
| `learning_rate` | float | 1e-5 (Whisper) / 1e-4 (Wav2Vec2) | Tasa de aprendizaje |
| `warmup_steps` | int | 100 | Pasos de calentamiento |
| `weight_decay` | float | 0.01 | Regularización L2 |
| `use_peft` | bool | false | Activar LoRA (eficiente en memoria) |
| `peft_r` | int | 16 | Rango del adaptador LoRA |
| `peft_alpha` | int | 32 | Alpha de LoRA |
| `whisper_language` | str | "es" | Idioma para Whisper |
| `whisper_task` | str | "transcribe" | Tarea Whisper |
| `fp16` | bool | auto (CUDA) | Precisión mixta |

**Notas para el frontend:**
- Llamar primero a `GET /api/entrenamiento/lenguas/` para mostrar el dropdown de lengua y el `lengua_id` correcto.
- Llamar a `GET /api/entrenamiento/modelos/` para el dropdown de modelo base.
- Para la selección de datos usar `GET /api/entrenamiento/dataset/sesiones/` y renderizar checkboxes individuales por jornada agrupados por comunidad.
- El contador de muestras seleccionadas se calcula en el cliente: sumar `etiquetados` de los ítems marcados.
- Solo habilitar "Lanzar entrenamiento" si el total de muestras seleccionadas ≥ 5.
- Después de recibir 202, redirigir automáticamente a la pantalla de monitoreo (HU-21).

---

### HU-21 — Monitorear el entrenamiento en tiempo real

**Como** investigador, **quiero** ver el estado del entrenamiento mientras avanza, **para** saber si está corriendo correctamente sin tener que esperar al final.

**Criterios de aceptación:**
- El frontend hace polling cada 10-15 segundos a este endpoint.
- Se puede ver: estado actual, muestras de train/eval, métricas parciales (si ya hay alguna época completa) y posibles errores.
- Cuando `estado == "completado"`, dejar de hacer polling y mostrar el botón de activar.
- Si `estado == "fallido"`, mostrar el `error_mensaje` en rojo.

```bash
curl http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-.../estado/

# Mientras entrena → estado: "entrenando"
{
  "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "nombre": "whisper-small-iku-v1",
  "lengua": "iku",
  "modelo": "openai/whisper-small",
  "estado": "entrenando",
  "is_active": false,
  "num_muestras_train": 55,
  "num_muestras_eval": 7,
  "metricas": {},
  "mlflow_run_id": "abc123def456",
  "mlflow_experiment_name": "sayta-asr-iku",
  "task_info": {
    "experimento_id": "7f3e4c2a-...",
    "started_at": "2026-06-01T10:30:00",
    "estado": "entrenando"
  },
  "error_mensaje": "",
  "created_at": "2026-06-01T10:30:00Z",
  "completed_at": null
}

# Al terminar → estado: "completado"
{
  "estado": "completado",
  "is_active": false,
  "num_muestras_train": 55,
  "num_muestras_eval": 7,
  "metricas": {
    "train_loss": 0.2134,
    "eval_loss": 0.3821,
    "eval_wer": 0.1820,
    "eval_cer": 0.0541,
    "total_steps": 280,
    "epochs": 20.0,
    "runtime_segundos": 3842.1
  },
  "mlflow_run_id": "abc123def456",
  "completed_at": "2026-06-01T11:34:02Z",
  "task_info": null
}

# Si falla → estado: "fallido"
{
  "estado": "fallido",
  "error_mensaje": "No se pudieron cargar muestras de audio. Verifica los archivos.",
  "task_info": null
}
```

**Métricas explicadas:**

| Métrica | Descripción | Valores típicos |
|---|---|---|
| `train_loss` | Pérdida de entrenamiento final | < 0.5 es bueno |
| `eval_loss` | Pérdida en set de evaluación | < 0.6 es bueno |
| `eval_wer` | Word Error Rate (0=perfecto, 1=pésimo) | < 0.30 es útil |
| `eval_cer` | Character Error Rate | < 0.15 es bueno |
| `total_steps` | Pasos totales de optimización | — |
| `epochs` | Épocas completadas | — |
| `runtime_segundos` | Duración total del entrenamiento | — |

**Notas para el frontend:**
- Mostrar un indicador de spinner/progreso mientras `estado == "entrenando"`.
- Al pasar a `estado == "completado"`, mostrar las métricas con colores: WER < 0.3 en verde, WER 0.3–0.5 en amarillo, WER > 0.5 en rojo.
- Mostrar link al dashboard de MLflow con el `mlflow_run_id` si está disponible.

---

### HU-22 — Ver historial de experimentos de entrenamiento

**Como** investigador, **quiero** ver todos los experimentos realizados filtrados por lengua o estado, **para** comparar resultados y elegir el mejor modelo para activar.

```bash
# Todos los experimentos
curl http://localhost:8000/api/entrenamiento/experimentos/

# Filtrar por lengua
curl "http://localhost:8000/api/entrenamiento/experimentos/?lengua_id=1"

# Solo los completados
curl "http://localhost:8000/api/entrenamiento/experimentos/?estado=completado"

# Respuesta 200
{
  "total": 3,
  "experimentos": [
    {
      "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
      "nombre": "whisper-small-iku-v2",
      "lengua_codigo": "iku",
      "lengua_nombre": "Arhuaco",
      "modelo_nombre": "openai/whisper-small",
      "comunidades_usadas": ["arhuaco"],
      "estado": "activo",
      "estado_display": "Activo",
      "is_active": true,
      "num_muestras_train": 55,
      "num_muestras_eval": 7,
      "metricas": {
        "eval_wer": 0.1820,
        "eval_cer": 0.0541,
        "train_loss": 0.2134
      },
      "created_at": "2026-06-01T10:30:00Z",
      "completed_at": "2026-06-01T11:34:02Z"
    },
    {
      "id": "3a1b2c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
      "nombre": "whisper-small-iku-v1",
      "lengua_codigo": "iku",
      "lengua_nombre": "Arhuaco",
      "modelo_nombre": "openai/whisper-small",
      "comunidades_usadas": ["arhuaco"],
      "estado": "completado",
      "estado_display": "Completado",
      "is_active": false,
      "num_muestras_train": 48,
      "num_muestras_eval": 5,
      "metricas": {
        "eval_wer": 0.2910,
        "eval_cer": 0.0873,
        "train_loss": 0.3412
      },
      "created_at": "2026-05-28T09:00:00Z",
      "completed_at": "2026-05-28T10:12:44Z"
    }
  ]
}
```

---

### HU-23 — Ver detalle de un experimento con métricas y configuración

**Como** investigador, **quiero** ver el detalle completo de un experimento (hiperparámetros, métricas, datos usados, referencia MLflow), **para** entender exactamente cómo se obtuvo ese modelo.

```bash
curl http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-.../

# Respuesta 200
{
  "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "nombre": "whisper-small-iku-v2",
  "lengua_codigo": "iku",
  "lengua_nombre": "Arhuaco",
  "modelo_base_info": {
    "id": 1,
    "nombre_hf": "openai/whisper-small",
    "tipo": "whisper",
    "tipo_display": "Whisper (Seq2Seq)",
    "descargado": true
  },
  "comunidades_usadas": ["arhuaco"],
  "estado": "activo",
  "estado_display": "Activo",
  "is_active": true,
  "config_entrenamiento": {
    "num_train_epochs": 20,
    "learning_rate": 1e-5,
    "per_device_train_batch_size": 4,
    "gradient_accumulation_steps": 2,
    "use_peft": false,
    "whisper_language": "es"
  },
  "ruta_modelo_entrenado": "/app/modelos_entrenados/7f3e4c2a-...",
  "mlflow_run_id": "abc123def456",
  "mlflow_experiment_id": "1",
  "mlflow_experiment_name": "sayta-asr-iku",
  "mlflow_tracking_uri": "/app/mlruns",
  "metricas": {
    "train_loss": 0.2134,
    "eval_loss": 0.3821,
    "eval_wer": 0.1820,
    "eval_cer": 0.0541,
    "total_steps": 280,
    "epochs": 20.0,
    "runtime_segundos": 3842.1
  },
  "num_muestras_train": 55,
  "num_muestras_eval": 7,
  "error_mensaje": "",
  "task_id": "",
  "created_at": "2026-06-01T10:30:00Z",
  "completed_at": "2026-06-01T11:34:02Z"
}
```

**Notas para el frontend:**
- Mostrar las métricas en una tabla comparativa si hay más de un experimento completado para la misma lengua.
- El `mlflow_run_id` puede usarse para construir la URL del dashboard MLflow:
  `http://localhost:5000/#/experiments/{mlflow_experiment_id}/runs/{mlflow_run_id}`
- Mostrar el botón "Activar este modelo" solo si `estado == "completado"` y `is_active == false`.

---

### HU-24 — Activar un modelo entrenado para una lengua

**Como** investigador, **quiero** marcar un experimento completado como el modelo activo para su lengua, **para** que los endpoints de transcripción y traducción lo usen automáticamente.

**Criterios de aceptación:**
- Solo se puede activar un experimento con `estado == "completado"` o `estado == "activo"`.
- Al activar, cualquier experimento previamente activo de la misma lengua pasa a `completado`.
- Solo puede haber un modelo activo por lengua.
- La ruta del modelo en disco debe existir.

```bash
curl -X POST http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-.../activar/

# Respuesta 200
{
  "mensaje": "Modelo activado para lengua \"Arhuaco\".",
  "experimento_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "lengua": "iku",
  "ruta_modelo": "/app/modelos_entrenados/7f3e4c2a-...",
  "mlflow_run_id": "abc123def456"
}

# Estado no permite activar → 422
{
  "error": "No se puede activar un experimento con estado \"entrenando\". Debe estar en estado \"completado\" o \"activo\"."
}

# Modelo no existe en disco → 422
{
  "error": "La ruta del modelo entrenado no existe en disco."
}
```

---

### HU-25 — Transcribir un audio con el modelo activo de una lengua

**Como** usuario del sistema, **quiero** enviar un archivo de audio y obtener la transcripción en texto usando el modelo ASR fine-tuneado para esa lengua, **para** digitalizar grabaciones en lengua indígena.

**Criterios de aceptación:**
- Se recibe el archivo de audio como `multipart/form-data`.
- Extensiones permitidas: `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.mp4`.
- Si la lengua no tiene modelo ASR activo → 422 con instrucción de entrenar y activar.
- El modelo se carga en memoria con caché (la primera carga puede tardar unos segundos).

```bash
curl -X POST http://localhost:8000/api/entrenamiento/transcribir/ \
  -F "lengua_id=1" \
  -F "audio=@grabacion_saludos.wav"

# Respuesta 200
{
  "lengua": "iku",
  "modelo": "whisper-small-iku-v2",
  "transcripcion": "Du zari bunsi chano"
}

# Sin modelo activo → 422
{
  "error": "La lengua \"Arhuaco\" no tiene un modelo ASR activo. Entrena y activa un modelo con POST /api/entrenamiento/entrenar/ y POST /api/entrenamiento/experimentos/{id}/activar/"
}

# Extensión no permitida → 400
{
  "error": "Extensión \".docx\" no permitida. Usa: .wav, .mp3, .ogg, .flac, .m4a, .mp4"
}
```

---

### HU-26 — Pipeline completo: audio → transcripción → traducción

**Como** usuario del traductor, **quiero** enviar un audio en lengua indígena y recibir directamente la transcripción y su traducción al español, **para** comprender el contenido sin necesidad de dos pasos separados.

**Criterios de aceptación:**
- El audio se transcribe con el modelo ASR activo para la lengua.
- La transcripción entra al pipeline de traducción semántica (FAISS + embeddings activos).
- Si hay modelo ASR activo pero no hay embedding activo → se devuelve la transcripción con advertencia.
- Si no hay modelo ASR activo → 422.
- La dirección de traducción por defecto es `lengua_a_es`.

```bash
curl -X POST http://localhost:8000/api/entrenamiento/transcribir-y-traducir/ \
  -F "lengua_id=1" \
  -F "audio=@grabacion.wav" \
  -F "direccion=lengua_a_es" \
  -F "top_k=3"

# Respuesta 200 — pipeline completo exitoso
{
  "lengua": "iku",
  "modelo_asr": "whisper-small-iku-v2",
  "transcripcion": "Du zari bunsi chano",
  "traduccion": {
    "direccion": "iku→es",
    "embedding_version": "20260601_103000",
    "conclusion": {
      "termino": "Du zari bunsi chano",
      "termino_es": "buenos días",
      "definicion": "Saludo de la mañana en lengua ikʉn.",
      "probabilidad": 52.4
    },
    "resultados": [
      {
        "termino": "Du zari bunsi chano",
        "termino_es": "buenos días",
        "definicion": "Saludo de la mañana en lengua ikʉn.",
        "score": 0.9801,
        "probabilidad": 52.4,
        "mejor_coincidencia": true,
        "coincidencia": "Du zari bunsi chano"
      },
      {
        "termino": "Du zari ɉwi nayo",
        "termino_es": "buenas tardes",
        "definicion": "Saludo de la tarde en lengua ikʉn.",
        "score": 0.8740,
        "probabilidad": 41.2,
        "mejor_coincidencia": false,
        "coincidencia": "Du zari"
      },
      {
        "termino": "Bunachʉn",
        "termino_es": "español",
        "definicion": "Nombre del español o castellano en lengua ikʉn.",
        "score": 0.2680,
        "probabilidad": 6.4,
        "mejor_coincidencia": false,
        "coincidencia": "chano"
      }
    ]
  }
}

# Transcripción OK pero sin embedding → advertencia en traducción
{
  "lengua": "iku",
  "modelo_asr": "whisper-small-iku-v2",
  "transcripcion": "Du zari bunsi chano",
  "traduccion": {
    "advertencia": "La lengua \"Arhuaco\" no tiene embedding activo. Genera y activa uno con /api/terminos/embeddings/."
  }
}
```

---

## Flujo completo de entrenamiento paso a paso

```bash
# ── PASO 1: Ver lenguas del sistema y estado de sus modelos ASR ───────────
curl http://localhost:8000/api/entrenamiento/lenguas/
# → [{"id": 1, "codigo": "iku", "nombre": "Arhuaco", "tiene_modelo_activo": false, ...}]
# → Anota el "id" de la lengua para usarlo como lengua_id más adelante

# ── PASO 2: Ver resumen de datos etiquetados disponibles ──────────────────
curl http://localhost:8000/api/entrenamiento/dataset/
# → Ver comunidades, etiquetados totales, apto_para_entrenamiento

# ── PASO 2b: Ver todas las jornadas disponibles para selección granular ────
curl http://localhost:8000/api/entrenamiento/dataset/sesiones/
# → Lista plana de jornadas; úsala para renderizar checkboxes en el frontend

# ── PASO 2c (opcional): Ver detalle de una comunidad específica ────────────
curl http://localhost:8000/api/entrenamiento/dataset/arhuaco/
# → Jornadas de arhuaco con sus porcentajes de etiquetado

# ── PASO 3: Ver catálogo de modelos disponibles ───────────────────────────
curl http://localhost:8000/api/entrenamiento/modelos-disponibles/
# → 5 modelos curados; descargado: true/false

# ── PASO 4: Descargar el modelo elegido ───────────────────────────────────
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{"nombre_hf": "openai/whisper-small", "tipo": "whisper"}'
# → {"modelo": {"id": 1, ...}}   ← anota el "id" como modelo_audio_id

# ── PASO 5: Lanzar entrenamiento (elige uno de los tres modos) ────────────

# Modo A — jornadas específicas (recomendado para máximo control)
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "whisper-small-iku-fauna-v1",
    "lengua_id": 1,
    "modelo_audio_id": 1,
    "sesiones": [
      {"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"},
      {"comunidad": "arhuaco", "jornada": "grabacion_22_03_26_territorio"}
    ],
    "config": {"num_train_epochs": 20, "learning_rate": 1e-5}
  }'

# Modo B — comunidades completas
# "comunidades": ["arhuaco"]

# Modo C — todo el dataset disponible
# "todos": true

# → {"experimento_id": "7f3e4c2a-...", "num_muestras": 44, "estado_url": "..."}

# ── PASO 6: Monitorear (polling cada 15s hasta completado) ────────────────
curl http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-.../estado/
# → {"estado": "entrenando", ...}  ← repetir hasta:
# → {"estado": "completado", "metricas": {"eval_wer": 0.18, ...}}

# ── PASO 7: Activar el modelo entrenado ───────────────────────────────────
curl -X POST http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-.../activar/
# → {"mensaje": "Modelo activado para lengua \"Arhuaco\"."}

# ── PASO 8: Transcribir un audio ──────────────────────────────────────────
curl -X POST http://localhost:8000/api/entrenamiento/transcribir/ \
  -F "lengua_id=1" \
  -F "audio=@mi_grabacion.wav"
# → {"transcripcion": "Du zari bunsi chano"}

# ── PASO 9: Pipeline completo audio → traducción ──────────────────────────
curl -X POST http://localhost:8000/api/entrenamiento/transcribir-y-traducir/ \
  -F "lengua_id=1" \
  -F "audio=@mi_grabacion.wav" \
  -F "direccion=lengua_a_es"
# → {"transcripcion": "Du zari bunsi chano", "traduccion": {"conclusion": {"termino_es": "buenos días", ...}}}
```

---

## Tabla de endpoints — Épica 6

| Método | Endpoint | Descripción | HU |
|---|---|---|---|
| GET | `/api/entrenamiento/lenguas/` | Lenguas del sistema con estado ASR | HU-15 |
| GET | `/api/entrenamiento/dataset/` | Stats de datos etiquetados por comunidad | HU-15b |
| GET | `/api/entrenamiento/dataset/sesiones/` | Lista plana de todas las jornadas (checkboxes) | HU-15c |
| GET | `/api/entrenamiento/dataset/{community}/` | Detalle por jornada de una comunidad | HU-16 |
| GET | `/api/entrenamiento/modelos-disponibles/` | Catálogo curado de modelos HF | HU-17 |
| POST | `/api/entrenamiento/modelos/descargar/` | Descargar modelo desde HF Hub | HU-18 |
| GET | `/api/entrenamiento/modelos/` | Modelos descargados localmente | HU-19 |
| POST | `/api/entrenamiento/entrenar/` | Lanzar fine-tuning — 3 modos de selección (asíncrono) | HU-20 |
| GET | `/api/entrenamiento/experimentos/{id}/estado/` | Polling del entrenamiento | HU-21 |
| GET | `/api/entrenamiento/experimentos/` | Historial de experimentos | HU-22 |
| GET | `/api/entrenamiento/experimentos/{id}/` | Detalle con métricas y config | HU-23 |
| POST | `/api/entrenamiento/experimentos/{id}/activar/` | Activar modelo para su lengua | HU-24 |
| POST | `/api/entrenamiento/transcribir/` | Audio → texto (modelo activo) | HU-25 |
| POST | `/api/entrenamiento/transcribir-y-traducir/` | Audio → texto → traducción | HU-26 |

---

## Notas de integración para el frontend — Épica 6

### Pantalla: Panel de estado de lenguas

1. Al cargar la sección de entrenamiento, llamar primero a `GET /api/entrenamiento/lenguas/`.
2. Mostrar una tarjeta por lengua con badge "Modelo activo ✓" o "Sin modelo ASR".
3. En la tarjeta activa mostrar las métricas del modelo (WER, CER) y la fecha de entrenamiento.
4. El `id` de cada lengua es el `lengua_id` para todos los formularios siguientes.

### Pantalla: Explorador de datos (antes de entrenar)

**Vista rápida (por comunidad):**
1. `GET /api/entrenamiento/dataset/` → tarjetas con barra de progreso de etiquetado por comunidad.
2. Al expandir, `GET /api/entrenamiento/dataset/{community}/` → acordeón de jornadas.

**Vista granular (recomendada para selección de datos):**
1. `GET /api/entrenamiento/dataset/sesiones/` → lista plana de todas las jornadas.
2. Renderizar checkboxes individuales agrupados por comunidad.
3. Incluir "Seleccionar todo — Arhuaco" y "Seleccionar todo — Kogui" como atajos.
4. Deshabilitar en gris las jornadas con `apta: false`.
5. Calcular en el cliente el total de muestras seleccionadas (sumar `etiquetados` de los ítems marcados).
6. Solo habilitar "Lanzar entrenamiento" si el total ≥ 5.

### Pantalla: Configuración de entrenamiento

1. **Dropdown de lengua** → `GET /api/entrenamiento/lenguas/` (usar campo `id` como `lengua_id`).
2. **Dropdown de modelo base** → `GET /api/entrenamiento/modelos/` (solo los con `descargado: true`). Si está vacío, mostrar enlace a "Descargar modelo" (HU-18).
3. **Selector de datos** → tres opciones de radio:
   - "Usar todos los audios del sistema" → `"todos": true`
   - "Por comunidades completas" → `"comunidades": [...]`
   - "Selección manual por jornadas" → `"sesiones": [{comunidad, jornada}]` (checkboxes de HU-15c)
4. **Sección colapsable "Configuración avanzada"** con los hiperparámetros de la tabla de HU-20.
5. Al enviar → `POST /api/entrenamiento/entrenar/` → redirigir al monitor con el `experimento_id`.

### Pantalla: Monitor de entrenamiento

1. Polling a `GET /api/entrenamiento/experimentos/{id}/estado/` cada 15 segundos.
2. Barra de progreso indeterminada mientras `estado == "entrenando"`.
3. Al llegar a `estado == "completado"`, mostrar métricas coloreadas (WER < 0.3 verde, 0.3–0.5 amarillo, > 0.5 rojo) y botón "Activar este modelo".
4. Si `estado == "fallido"`, mostrar `error_mensaje` en rojo y botón "Volver a intentar".
5. Si `mlflow_run_id` está presente, mostrar enlace al dashboard de MLflow.

### Pantalla: Historial de experimentos

1. Tabla filtrable por lengua (`?lengua_id=`) y estado (`?estado=`).
2. Columnas: nombre, lengua, modelo HF, WER, CER, muestras, fecha, estado (badge coloreado).
3. Fila con `is_active: true` → badge "ACTIVO" en verde.
4. Fila con `estado == "completado"` y `is_active: false` → botón "Activar".
5. `comunidades_usadas` en el detalle (HU-23) ahora tiene estructura `{modo, sesiones/comunidades}` — mostrarla como resumen legible.

---

---

## Apéndice A — Variables de entorno y configuración del servidor

> Esta sección es para el equipo de infraestructura / DevOps.
> El frontend **no** configura estas variables — las necesita el backend.

### Referencia completa de variables de entorno

#### Django — Seguridad y acceso

| Variable | Obligatoria | Default desarrollo | Descripción |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | **Sí** | *(insecura hardcodeada)* | Clave secreta. Generar con `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | No | `True` | Poner en `False` en producción |
| `DJANGO_ALLOWED_HOSTS` | **Sí en prod** | `*` | Hosts que puede responder el backend (ej. `api.sayta.co,localhost`) |
| `CSRF_TRUSTED_ORIGINS` | **Sí en prod** | *(vacío)* | URL del frontend para evitar errores CSRF (ej. `https://sayta.co`) |

```bash
# Generar SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

#### PostgreSQL — Base de datos

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `POSTGRES_HOST` | No* | *(usa SQLite si no existe)* | Host de PostgreSQL — si no se define, Django usa SQLite local |
| `POSTGRES_PORT` | No | `5432` | Puerto |
| `POSTGRES_DB` | No | `sayta_db` | Nombre de la base de datos |
| `POSTGRES_USER` | No | `postgres` | Usuario de aplicación |
| `POSTGRES_PASSWORD` | **Sí si hay PG** | *(vacío)* | Contraseña |
| `DB_CONN_MAX_AGE` | No | `60` (dev) / `300` (prod) | Segundos de vida de conexiones persistentes |

> *Si `POSTGRES_HOST` **no** está definida, Django usa SQLite en `db.sqlite3`. Ideal para desarrollo local sin Docker.

---

#### Embeddings de términos (módulo `terminos`)

| Variable | Default desarrollo | Default producción | Descripción |
|---|---|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | igual | Modelo HuggingFace para generar embeddings de diccionario |
| `EMBEDDINGS_STORAGE_DIR` | `<proyecto>/embeddings_storage` | `/mnt/app_storage/embeddings_storage` | Índices FAISS por lengua |
| `ETTE_EMBEDDINGS_DIR` | `<proyecto>/translator_api/embeddings` | `/app/translator_api/embeddings` | Artefactos legacy del traductor Ette |

---

#### HuggingFace — Caché de modelos

| Variable | Default desarrollo | Default producción | Descripción |
|---|---|---|---|
| `HF_HOME` | *(caché del SO, suele ser `~/.cache/huggingface`)* | `/mnt/models` | Directorio raíz de caché de HuggingFace |
| `TRANSFORMERS_CACHE` | *(caché del SO)* | `/mnt/models/transformers` | Caché específico de la librería `transformers` |

> Definir `HF_HOME` en un volumen persistente **evita re-descargar** modelos pesados (Whisper ~460 MB, Wav2Vec2 XLSR ~1.2 GB) cada vez que se reinicia el contenedor.

---

#### Módulo de entrenamiento ASR (`entrenamiento`) ← nuevas

| Variable | Default desarrollo | Default producción | Descripción |
|---|---|---|---|
| `AUDIO_MODELS_DIR` | `<proyecto>/audio_models` | `/mnt/app_storage/audio_models` | Modelos HF descargados listos para fine-tuning |
| `MODELOS_ENTRENADOS_DIR` | `<proyecto>/modelos_entrenados` | `/mnt/app_storage/modelos_entrenados` | Modelos fine-tuneados resultado de cada experimento |
| `MLFLOW_TRACKING_URI` | `<proyecto>/mlruns` | `/mnt/app_storage/mlruns` | URI del servidor MLflow para tracking de métricas |

**Opciones para `MLFLOW_TRACKING_URI`:**

```bash
# Opción 1 — Carpeta local (desarrollo, sin infraestructura extra)
MLFLOW_TRACKING_URI=/mnt/app_storage/mlruns

# Opción 2 — PostgreSQL (producción, métricas persistentes en BD)
MLFLOW_TRACKING_URI=postgresql://sayta_app:password@db:5432/mlflow_db

# Opción 3 — Servidor MLflow dedicado
MLFLOW_TRACKING_URI=http://mlflow-server:5000
```

---

### Archivo `.env` completo de referencia

```ini
# ============================================================
# .env — Sayta Backend
# Copiar como .env y reemplazar valores de ejemplo.
# NUNCA commitear este archivo con valores reales.
# ============================================================

# ── Django ────────────────────────────────────────────────────
DJANGO_SECRET_KEY=cambia-esto-con-el-comando-de-arriba
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api.sayta.co
CSRF_TRUSTED_ORIGINS=http://localhost:3000,https://sayta.co

# ── PostgreSQL ────────────────────────────────────────────────
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=sayta_db
POSTGRES_USER=sayta_app
POSTGRES_PASSWORD=contraseña-segura
DB_CONN_MAX_AGE=300

# ── Embeddings ────────────────────────────────────────────────
EMBEDDING_MODEL=intfloat/multilingual-e5-base
EMBEDDINGS_STORAGE_DIR=/mnt/app_storage/embeddings_storage
ETTE_EMBEDDINGS_DIR=/app/translator_api/embeddings

# ── HuggingFace caché ─────────────────────────────────────────
HF_HOME=/mnt/models
TRANSFORMERS_CACHE=/mnt/models/transformers

# ── Entrenamiento ASR ─────────────────────────────────────────
AUDIO_MODELS_DIR=/mnt/app_storage/audio_models
MODELOS_ENTRENADOS_DIR=/mnt/app_storage/modelos_entrenados
MLFLOW_TRACKING_URI=/mnt/app_storage/mlruns
```

---

### Volúmenes persistentes necesarios en producción

```
/mnt/app_storage/              ← Volumen NVMe montado en el contenedor
├── embeddings_storage/        ← EMBEDDINGS_STORAGE_DIR
│   ├── iku/
│   │   └── 20260601_103000/
│   │       ├── embeddings.npy
│   │       ├── faiss_index.bin
│   │       └── metadata.json
│   └── kogui/
│       └── ...
├── audio_models/              ← AUDIO_MODELS_DIR  (~500MB–2GB por modelo)
│   ├── openai__whisper-small/
│   └── facebook__wav2vec2-large-xlsr-53/
├── modelos_entrenados/        ← MODELOS_ENTRENADOS_DIR (~200–800MB por experimento)
│   └── 7f3e4c2a-1b5d-4a8e.../
│       ├── config.json
│       ├── model.safetensors
│       ├── preprocessor_config.json
│       └── training_config.json
├── mlruns/                    ← MLFLOW_TRACKING_URI (si se usa carpeta local)
│   └── 1/
│       └── abc123def456/
│           ├── metrics/
│           └── params/
└── staticfiles/

/mnt/models/                   ← HF_HOME  (caché de descarga de modelos HF)
├── hub/
└── transformers/
```

---

### Cómo levantar el backend en desarrollo local (sin Docker)

```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Variables mínimas de entorno (SQLite automático)
export DJANGO_SECRET_KEY="dev-key-no-usar-en-produccion"
export DJANGO_DEBUG="True"

# 4. Migraciones
python manage.py migrate

# 5. Servidor
python manage.py runserver

# Swagger disponible en:
# http://localhost:8000/api/docs/
```

---

## Apéndice B — Tabla global de todos los endpoints

> URL base: `http://localhost:8000`

### Salud del sistema

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health/` | Estado del servidor |

### Términos y embeddings (`/api/terminos/`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET / POST | `/api/terminos/lenguas/` | Listar / crear lenguas |
| GET / PUT / PATCH / DELETE | `/api/terminos/lenguas/{id}/` | Detalle / editar / eliminar lengua |
| GET / POST | `/api/terminos/terminos-es/` | Listar / crear términos en español |
| GET / POST | `/api/terminos/terminos/` | Listar / crear términos en lengua indígena |
| GET / PUT / PATCH / DELETE | `/api/terminos/terminos/{id}/` | Detalle / editar término |
| POST | `/api/terminos/terminos/{id}/restaurar/` | Reactivar término desactivado |
| POST | `/api/terminos/terminos/carga-masiva/` | Carga masiva desde JSON |
| POST | `/api/terminos/embeddings/generar/` | Generar embeddings (asíncrono) |
| GET | `/api/terminos/embeddings/estado/{task_id}/` | Polling del estado de generación |
| GET | `/api/terminos/embeddings/` | Listar versiones de embeddings |
| POST | `/api/terminos/embeddings/{id}/activar/` | Activar versión de embedding |

### Traducción texto a texto (`/api/traduccion/`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET / POST | `/api/traduccion/traducir/` | Traducir texto con pipeline semántico |

### Grabaciones y etiquetado (`/api/`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/grabaciones/` | Resumen de todas las comunidades |
| GET | `/api/grabaciones/{community}/` | Jornadas de una comunidad |
| GET | `/api/grabaciones/{community}/{session}/audios/` | Audios de una jornada |
| GET | `/api/grabaciones/{community}/{session}/audios/{filename}` | Descargar audio |
| GET | `/api/grabaciones/{community}/{session}/glosario/` | Glosario de la jornada |
| POST | `/api/grabaciones/{community}/{session}/etiquetar/` | Crear etiqueta para audio |
| GET / PUT / DELETE | `/api/grabaciones/{community}/{session}/etiqueta/{filename}/` | Leer / actualizar / eliminar etiqueta |
| GET | `/api/grabaciones/{community}/{session}/estado/` | Estado de etiquetado de la jornada |

### Entrenamiento ASR (`/api/entrenamiento/`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/entrenamiento/lenguas/` | Lenguas activas con estado de modelos ASR |
| GET | `/api/entrenamiento/modelos-disponibles/` | Catálogo de modelos HF recomendados |
| GET | `/api/entrenamiento/modelos/` | Modelos descargados localmente |
| POST | `/api/entrenamiento/modelos/descargar/` | Descargar modelo desde HF Hub |
| GET | `/api/entrenamiento/dataset/` | Stats de datos etiquetados por comunidad |
| GET | `/api/entrenamiento/dataset/sesiones/` | Lista plana de todas las jornadas (para checkboxes) |
| GET | `/api/entrenamiento/dataset/{community}/` | Detalle por jornada de una comunidad |
| POST | `/api/entrenamiento/entrenar/` | Lanzar fine-tuning — 3 modos: todos/sesiones/comunidades |
| GET | `/api/entrenamiento/experimentos/` | Historial de experimentos |
| GET | `/api/entrenamiento/experimentos/{id}/` | Detalle con métricas y config |
| GET | `/api/entrenamiento/experimentos/{id}/estado/` | Polling del entrenamiento |
| POST | `/api/entrenamiento/experimentos/{id}/activar/` | Activar modelo para su lengua |
| POST | `/api/entrenamiento/transcribir/` | Transcribir audio con modelo activo |
| POST | `/api/entrenamiento/transcribir-y-traducir/` | Audio → texto → traducción |

### Documentación automática

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/docs/` | Swagger UI interactivo |
| GET | `/api/schema/` | OpenAPI JSON schema |
