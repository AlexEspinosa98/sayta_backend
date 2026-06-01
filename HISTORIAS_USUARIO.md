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
