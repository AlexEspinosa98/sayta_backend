# Módulo de Entrenamiento ASR — Guía de Integración Frontend
## Proyecto Sayta — Traductor de Lenguas Indígenas

> **Base URL:** `http://localhost:8000`
> **Módulo:** `GET/POST /api/entrenamiento/`
> **Swagger interactivo:** `http://localhost:8000/api/docs/`

---

## Índice

1. [Flujo general de pantallas](#1-flujo-general-de-pantallas)
2. [Estado global que el frontend debe mantener](#2-estado-global-que-el-frontend-debe-mantener)
3. [Pantalla 1 — Panel de lenguas y estado ASR](#3-pantalla-1--panel-de-lenguas-y-estado-asr)
4. [Pantalla 2 — Catálogo de modelos + descarga](#4-pantalla-2--catálogo-de-modelos--descarga)
5. [Pantalla 3 — Explorador de datos etiquetados](#5-pantalla-3--explorador-de-datos-etiquetados)
6. [Pantalla 4 — Formulario de entrenamiento](#6-pantalla-4--formulario-de-entrenamiento)
7. [Pantalla 5 — Monitor de entrenamiento (polling)](#7-pantalla-5--monitor-de-entrenamiento-polling)
8. [Pantalla 6 — Historial de experimentos](#8-pantalla-6--historial-de-experimentos)
9. [Pantalla 7 — Activar modelo entrenado](#9-pantalla-7--activar-modelo-entrenado)
10. [Pantalla 8 — Transcribir audio](#10-pantalla-8--transcribir-audio)
11. [Pantalla 9 — Pipeline completo audio → traducción](#11-pantalla-9--pipeline-completo-audio--traducción)
12. [Tabla resumen de todos los endpoints](#12-tabla-resumen-de-todos-los-endpoints)
13. [Catálogo de errores y cómo mostrarlos](#13-catálogo-de-errores-y-cómo-mostrarlos)

---

## 1. Flujo general de pantallas

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MÓDULO DE ENTRENAMIENTO ASR                          │
└─────────────────────────────────────────────────────────────────────────┘

[Pantalla 1: Panel de lenguas]
   └── GET /api/entrenamiento/lenguas/
       ↓ Guarda: lengua.id, lengua.codigo, tiene_modelo_activo
       ↓
[Pantalla 2: Catálogo de modelos]
   └── GET /api/entrenamiento/modelos-disponibles/
   └── GET /api/entrenamiento/modelos/
       ↓ Si modelo no descargado:
       └── POST /api/entrenamiento/modelos/descargar/   (bloquea, esperar respuesta)
       ↓ Guarda: modelo.id (como modelo_audio_id)
       ↓
[Pantalla 3: Explorador de datos]
   └── GET /api/entrenamiento/dataset/                  (vista resumen)
   └── GET /api/entrenamiento/dataset/sesiones/         (lista plana con checkboxes)
   └── GET /api/entrenamiento/dataset/{community}/      (detalle comunidad, opcional)
       ↓ Guarda: lista de {comunidad, jornada} seleccionadas
       ↓ O: todos=true / comunidades=[...]
       ↓
[Pantalla 4: Formulario de entrenamiento]
   └── Usa: lengua.id, modelo.id, seleccion de datos, config hiperparámetros
   └── POST /api/entrenamiento/entrenar/
       ↓ Recibe: experimento_id, estado_url
       ↓
[Pantalla 5: Monitor de entrenamiento]  ← polling cada 15s
   └── GET /api/entrenamiento/experimentos/{id}/estado/
       ↓ Cuando estado == "completado":
       └── POST /api/entrenamiento/experimentos/{id}/activar/
       ↓
[Pantalla 6: Historial de experimentos]
   └── GET /api/entrenamiento/experimentos/
   └── GET /api/entrenamiento/experimentos/{id}/        (detalle)

[Pantalla 8: Transcripción]             ← requiere modelo activo
   └── POST /api/entrenamiento/transcribir/

[Pantalla 9: Pipeline completo]         ← requiere modelo activo + embedding activo
   └── POST /api/entrenamiento/transcribir-y-traducir/
```

---

## 2. Estado global que el frontend debe mantener

El frontend debe mantener este estado entre pantallas (puede ser Context/Store/Zustand/Redux):

```typescript
interface TrainingModuleState {
  // De Pantalla 1
  lenguaSeleccionada: {
    id: number;
    codigo: string;       // "iku" | "kogui"
    nombre: string;       // "Arhuaco" | "Kogui"
    tiene_modelo_activo: boolean;
    modelo_activo: ModeloActivoInfo | null;
  } | null;

  // De Pantalla 2
  modeloSeleccionado: {
    id: number;           // modelo_audio_id para el POST de entrenar
    nombre_hf: string;    // "openai/whisper-small"
    tipo: "whisper" | "wav2vec2";
  } | null;

  // De Pantalla 3 (según modo de selección)
  modoSeleccion: "todos" | "sesiones" | "comunidades" | null;
  sesionesSeleccionadas: Array<{ comunidad: string; jornada: string }>;
  comunidadesSeleccionadas: string[];
  totalMuestrasSeleccionadas: number;   // calculado en cliente

  // De Pantalla 4 (después de POST /entrenar/)
  experimentoActivo: {
    id: string;           // UUID
    estado_url: string;
    nombre: string;
  } | null;
}
```

---

## 3. Pantalla 1 — Panel de lenguas y estado ASR

### Propósito
Primera pantalla del módulo. Muestra el estado actual de cada lengua: si ya tiene un modelo ASR entrenado y activo, las métricas del modelo actual, y qué modelos base están disponibles para entrenar.

### Cuándo llamar este endpoint
- Al montar la pantalla (una vez).
- Después de activar un modelo (refrescar).

### Request

```http
GET /api/entrenamiento/lenguas/
```

```bash
curl http://localhost:8000/api/entrenamiento/lenguas/
```

### Response 200

```json
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

### Qué hace el frontend con esta respuesta

| Campo | Acción en UI |
|---|---|
| `id` | Guardar como `lenguaSeleccionada.id` al hacer clic en la tarjeta |
| `tiene_modelo_activo: true` | Badge verde "Modelo activo ✓" |
| `tiene_modelo_activo: false` | Badge gris "Sin modelo ASR" |
| `modelo_activo.metricas.eval_wer` | Mostrar "WER: 18.2%" con color según rango |
| `ultimo_experimento.estado == "fallido"` | Advertencia naranja "El último entrenamiento falló" |
| `modelos_disponibles_para_entrenar.length == 0` | Botón "Entrenar" deshabilitado + tooltip "Descarga primero un modelo base" |

### Qué guardar en estado global al seleccionar una lengua

```javascript
// Al hacer clic en la tarjeta de una lengua:
setState({
  lenguaSeleccionada: {
    id: lengua.id,           // → lengua_id en POST /entrenar/
    codigo: lengua.codigo,
    nombre: lengua.nombre,
    tiene_modelo_activo: lengua.tiene_modelo_activo,
    modelo_activo: lengua.modelo_activo,
  }
});
// Navegar a Pantalla 2 o directamente al formulario si ya hay modelos descargados
```

---

## 4. Pantalla 2 — Catálogo de modelos + descarga

### Propósito
Mostrar los modelos ASR disponibles para fine-tuning. Permitir descargar los que no estén en el servidor. Un modelo debe estar descargado antes de poder entrenar con él.

### Flujo de esta pantalla

```
Montar pantalla
    ↓
GET /api/entrenamiento/modelos-disponibles/   ← catálogo con estado descargado
GET /api/entrenamiento/modelos/               ← lista de los ya descargados
    ↓
Usuario hace clic en "Descargar" en un modelo
    ↓
POST /api/entrenamiento/modelos/descargar/    ← SINCRÓNICO, mostrar spinner
    ↓ esperar respuesta (puede tardar 2-10 min)
    ↓
Respuesta 201 → Refrescar catálogo → Modelo aparece como "Descargado ✓"
Usuario hace clic en "Usar este modelo"
    ↓
Guardar modelo.id en estado global
```

---

### 4.1 — GET Catálogo de modelos disponibles

```http
GET /api/entrenamiento/modelos-disponibles/
```

```bash
curl http://localhost:8000/api/entrenamiento/modelos-disponibles/
```

#### Response 200

```json
{
  "total": 5,
  "modelos": [
    {
      "nombre_hf": "openai/whisper-small",
      "tipo": "whisper",
      "descripcion": "Whisper Small — 244M parámetros. Multilingüe, excelente para fine-tuning en lenguas indígenas. Balance ideal rendimiento/tamaño.",
      "tamaño_aprox": "461 MB",
      "parametros": "244M",
      "recomendado": true,
      "gpu_requerida": false,
      "descargado": true,
      "id_bd": 1
    },
    {
      "nombre_hf": "openai/whisper-tiny",
      "tipo": "whisper",
      "descripcion": "Whisper Tiny — 39M parámetros. El más ligero; adecuado para hardware sin GPU o pruebas rápidas con pocos datos.",
      "tamaño_aprox": "151 MB",
      "parametros": "39M",
      "recomendado": false,
      "gpu_requerida": false,
      "descargado": false,
      "id_bd": null
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
      "descripcion": "Wav2Vec2 XLSR-53 — 315M parámetros. Pre-entrenado en 53 idiomas. Muy adecuado para fine-tuning con pocos datos.",
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
      "descripcion": "Wav2Vec2 Base — 95M parámetros. Más pequeño, solo inglés pre-entrenado.",
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

#### Qué hace el frontend

| Campo | Acción en UI |
|---|---|
| `recomendado: true` | Badge verde "Recomendado" |
| `gpu_requerida: true` | Badge amarillo "Requiere GPU" |
| `descargado: true` | Badge azul "Descargado ✓"; botón "Descargar" deshabilitado; botón "Seleccionar" habilitado |
| `descargado: false` | Botón "Descargar" habilitado; botón "Seleccionar" deshabilitado (tooltip: "Descarga primero") |
| `id_bd` | Si no es null, usar como `modelo_audio_id` al seleccionar |

---

### 4.2 — GET Modelos ya descargados

```http
GET /api/entrenamiento/modelos/
```

```bash
curl http://localhost:8000/api/entrenamiento/modelos/
```

#### Response 200

```json
{
  "total": 1,
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
    }
  ]
}
```

> Usar este endpoint para el **dropdown de modelos** en el formulario de entrenamiento.
> El `id` aquí es el `modelo_audio_id` que se envía en el POST de entrenar.

---

### 4.3 — POST Descargar un modelo

> **Importante:** Esta llamada es **sincrónica** y puede tardar de 2 a 10 minutos.
> El frontend debe mostrar un spinner bloqueante y NO permitir navegación durante la descarga.

```http
POST /api/entrenamiento/modelos/descargar/
Content-Type: application/json
```

#### Request body

```json
{
  "nombre_hf": "openai/whisper-small",
  "tipo": "whisper",
  "descripcion": "Whisper Small para IKU y KOGUI"
}
```

| Campo | Tipo | Requerido | Valores |
|---|---|---|---|
| `nombre_hf` | string | Sí | Nombre exacto del modelo en HuggingFace |
| `tipo` | string | Sí | `"whisper"` o `"wav2vec2"` |
| `descripcion` | string | No | Descripción libre |

```bash
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre_hf": "openai/whisper-small",
    "tipo": "whisper",
    "descripcion": "Whisper Small para IKU y KOGUI"
  }'
```

#### Response 201 — Descargado exitosamente

```json
{
  "mensaje": "openai/whisper-small descargado correctamente.",
  "modelo": {
    "id": 1,
    "nombre_hf": "openai/whisper-small",
    "tipo": "whisper",
    "tipo_display": "Whisper (Seq2Seq)",
    "descripcion": "Whisper Small para IKU y KOGUI",
    "ruta_local": "/app/audio_models/openai__whisper-small",
    "descargado": true,
    "created_at": "2026-06-01T10:00:00Z"
  }
}
```

#### Response 200 — Ya estaba descargado (idempotente)

```json
{
  "mensaje": "El modelo ya está descargado.",
  "modelo": { "id": 1, "nombre_hf": "openai/whisper-small", "descargado": true, ... }
}
```

#### Response 500 — Error de descarga

```json
{
  "error": "Repository 'openai/whisper-xxl' not found on HuggingFace Hub."
}
```

#### Qué hace el frontend después de 201/200

```javascript
// 1. Cerrar spinner de descarga
setDescargando(false);

// 2. Refrescar el catálogo para que el modelo aparezca como "Descargado ✓"
await fetchCatalogo();   // GET /api/entrenamiento/modelos-disponibles/

// 3. Guardar el id del modelo para el formulario
setState({
  modeloSeleccionado: {
    id: response.modelo.id,       // → modelo_audio_id en POST /entrenar/
    nombre_hf: response.modelo.nombre_hf,
    tipo: response.modelo.tipo,
  }
});
```

#### Ejemplos de descarga por tipo de modelo

```bash
# Whisper Tiny (más rápido, menos preciso — para pruebas)
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{"nombre_hf": "openai/whisper-tiny", "tipo": "whisper"}'

# Whisper Medium (más preciso — requiere GPU 8GB)
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{"nombre_hf": "openai/whisper-medium", "tipo": "whisper"}'

# Wav2Vec2 XLSR-53 (alternativa CTC, buen rendimiento con pocos datos)
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{"nombre_hf": "facebook/wav2vec2-large-xlsr-53", "tipo": "wav2vec2"}'

# Wav2Vec2 Base (más ligero)
curl -X POST http://localhost:8000/api/entrenamiento/modelos/descargar/ \
  -H "Content-Type: application/json" \
  -d '{"nombre_hf": "facebook/wav2vec2-base", "tipo": "wav2vec2"}'
```

---

## 5. Pantalla 3 — Explorador de datos etiquetados

### Propósito
Mostrar qué audios están disponibles y etiquetados para entrenamiento. Permite al investigador elegir exactamente qué datos usar: **todos**, por **jornadas individuales** (granular) o por **comunidades completas**.

### Flujo de esta pantalla

```
Montar pantalla
    ↓
GET /api/entrenamiento/dataset/           ← resumen por comunidad (tarjetas)
GET /api/entrenamiento/dataset/sesiones/  ← lista plana para checkboxes
    ↓
Usuario elige modo:
  [A] "Usar todos los datos"   → modoSeleccion = "todos"
  [B] "Seleccionar jornadas"   → renderizar checkboxes desde /dataset/sesiones/
  [C] "Por comunidades"        → renderizar checkboxes de comunidades desde /dataset/
    ↓ (opcional)
GET /api/entrenamiento/dataset/{community}/  ← al expandir una comunidad (modo B o C)
    ↓
Calcular totalMuestrasSeleccionadas en cliente
Guardar selección en estado global
```

---

### 5.1 — GET Resumen por comunidad

```http
GET /api/entrenamiento/dataset/
```

```bash
curl http://localhost:8000/api/entrenamiento/dataset/
```

#### Response 200

```json
{
  "base_path": "/mnt/sayta_data/data/Grabaciones",
  "existe": true,
  "total_comunidades": 2,
  "resumen_global": {
    "total_audios": 121,
    "etiquetados": 65,
    "sin_etiquetar": 56,
    "porcentaje_completado": 53.7
  },
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

#### Si el directorio no existe

```json
{
  "base_path": "/mnt/sayta_data/data/Grabaciones",
  "existe": false,
  "comunidades": [],
  "advertencia": "Directorio de grabaciones no encontrado."
}
```

---

### 5.2 — GET Lista plana de todas las jornadas (para checkboxes)

> **Este es el endpoint principal para la selección granular.**
> Una sola llamada devuelve TODAS las jornadas de TODAS las comunidades.

```http
GET /api/entrenamiento/dataset/sesiones/
```

```bash
curl http://localhost:8000/api/entrenamiento/dataset/sesiones/
```

#### Response 200

```json
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

#### Cómo construir los checkboxes en el frontend

```javascript
// Agrupar por comunidad para renderizar secciones
const grouped = sesiones.reduce((acc, s) => {
  if (!acc[s.comunidad]) acc[s.comunidad] = [];
  acc[s.comunidad].push(s);
  return acc;
}, {});

// Calcular muestras seleccionadas en tiempo real
const calcularTotal = (seleccionadas) =>
  seleccionadas.reduce((sum, s) => sum + s.etiquetados, 0);

// Mapa de checkbox individual
// key: `${s.comunidad}::${s.jornada}`
// value: { comunidad: s.comunidad, jornada: s.jornada }
// disabled: !s.apta
```

#### Renderizado esperado

```
┌─────────────────────────────────────────────────────────────┐
│  Selección de jornadas                   Total: 44 muestras │
├─────────────────────────────────────────────────────────────┤
│  📂 Arhuaco                              [☑ Seleccionar todo] │
│  ☑  grabacion_15_03_26_fauna        23/23 audios  ████████ 100% │
│  ☑  grabacion_22_03_26_territorio   21/31 audios  █████░░  67%  │
│  ☑  grabacion_05_04_26_cosmogonia   12/18 audios  █████░░  66%  │
│  ☐  grabacion_20_04_26_saludos       6/15 audios  ███░░░░  40%  │
├─────────────────────────────────────────────────────────────┤
│  📂 Kogui                               [☐ Seleccionar todo] │
│  ☐  grabacion_10_03_26_rituales      3/12 audios  ██░░░░░  25%  │
│  ░  grabacion_01_05_26_naturaleza    0/ 8 audios  ░░░░░░░   0%  (deshabilitado) │
└─────────────────────────────────────────────────────────────┘
```

---

### 5.3 — GET Detalle de una comunidad (opcional)

Usar cuando el usuario expande una comunidad para ver más información.

```http
GET /api/entrenamiento/dataset/{community}/
```

```bash
curl http://localhost:8000/api/entrenamiento/dataset/arhuaco/
```

#### Response 200

```json
{
  "comunidad": "arhuaco",
  "total_audios": 87,
  "etiquetados": 62,
  "apto_para_entrenamiento": true,
  "jornadas": [
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
    }
  ]
}
```

#### Response 404 — Comunidad no encontrada

```json
{
  "error": "Comunidad 'wiwa' no encontrada."
}
```

---

### Qué guardar en estado global al confirmar la selección de datos

```javascript
// Modo A — todos los datos del sistema
setState({
  modoSeleccion: "todos",
  sesionesSeleccionadas: [],
  comunidadesSeleccionadas: [],
  totalMuestrasSeleccionadas: dataset.resumen_global.etiquetados,
});

// Modo B — jornadas seleccionadas individualmente
const sesionesChecked = sesiones.filter(s => checkboxState[`${s.comunidad}::${s.jornada}`]);
setState({
  modoSeleccion: "sesiones",
  sesionesSeleccionadas: sesionesChecked.map(s => ({
    comunidad: s.comunidad,
    jornada: s.jornada,
  })),
  comunidadesSeleccionadas: [],
  totalMuestrasSeleccionadas: calcularTotal(sesionesChecked),
});

// Modo C — comunidades completas
setState({
  modoSeleccion: "comunidades",
  sesionesSeleccionadas: [],
  comunidadesSeleccionadas: comunidadesChecked,  // ["arhuaco", "kogui"]
  totalMuestrasSeleccionadas: calcularTotal(sesionesDeEsasComunidades),
});
```

---

## 6. Pantalla 4 — Formulario de entrenamiento

### Propósito
Pantalla de configuración final antes de lanzar el entrenamiento. Usa los datos acumulados de las pantallas anteriores:
- `lenguaSeleccionada.id` (de Pantalla 1)
- `modeloSeleccionado.id` (de Pantalla 2)
- `modoSeleccion` + `sesionesSeleccionadas` o `comunidadesSeleccionadas` (de Pantalla 3)

### POST Lanzar entrenamiento

```http
POST /api/entrenamiento/entrenar/
Content-Type: application/json
```

---

#### Modo A — Usar todos los datos del sistema

```json
{
  "nombre": "whisper-small-iku-full-v1",
  "lengua_id": 1,
  "modelo_audio_id": 1,
  "todos": true,
  "config": {
    "num_train_epochs": 20,
    "per_device_train_batch_size": 4,
    "gradient_accumulation_steps": 2,
    "learning_rate": 1e-5,
    "warmup_steps": 100,
    "whisper_language": "es",
    "use_peft": false
  }
}
```

```bash
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "whisper-small-iku-full-v1",
    "lengua_id": 1,
    "modelo_audio_id": 1,
    "todos": true,
    "config": {"num_train_epochs": 20, "learning_rate": 1e-5}
  }'
```

---

#### Modo B — Jornadas específicas (granular)

```json
{
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
}
```

```bash
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
    "config": {"num_train_epochs": 15}
  }'
```

---

#### Modo C — Comunidades completas

```json
{
  "nombre": "wav2vec2-xlsr-bilingue-v1",
  "lengua_id": 1,
  "modelo_audio_id": 2,
  "comunidades": ["arhuaco", "kogui"],
  "config": {
    "num_train_epochs": 30,
    "per_device_train_batch_size": 4,
    "learning_rate": 1e-4,
    "use_peft": true,
    "peft_r": 16,
    "peft_alpha": 32
  }
}
```

```bash
curl -X POST http://localhost:8000/api/entrenamiento/entrenar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "wav2vec2-xlsr-bilingue-v1",
    "lengua_id": 1,
    "modelo_audio_id": 2,
    "comunidades": ["arhuaco", "kogui"],
    "config": {"num_train_epochs": 30, "use_peft": true}
  }'
```

---

### Tabla de todos los campos del body

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `nombre` | string | **Sí** | Nombre descriptivo del experimento (ej. `"whisper-small-iku-v1"`) |
| `lengua_id` | int | **Sí** | `id` de la lengua (de `GET /api/entrenamiento/lenguas/`) |
| `modelo_audio_id` | int | **Sí** | `id` del modelo descargado (de `GET /api/entrenamiento/modelos/`) |
| `todos` | bool | Modo A | `true` → usa todos los audios etiquetados del sistema |
| `sesiones` | array | Modo B | Lista de `{comunidad, jornada}` (de `GET /api/entrenamiento/dataset/sesiones/`) |
| `comunidades` | array | Modo C | Lista de nombres de comunidad (de `GET /api/entrenamiento/dataset/`) |
| `config` | object | No | Hiperparámetros opcionales (ver tabla abajo) |

> **Regla:** Exactamente uno de `todos`, `sesiones` o `comunidades` debe estar presente y no vacío.

### Tabla de hiperparámetros en `config`

| Parámetro | Tipo | Default Whisper | Default Wav2Vec2 | Descripción |
|---|---|---|---|---|
| `num_train_epochs` | int | 20 | 20 | Épocas de entrenamiento |
| `per_device_train_batch_size` | int | 4 | 4 | Muestras por paso |
| `per_device_eval_batch_size` | int | 4 | 4 | Muestras en evaluación |
| `gradient_accumulation_steps` | int | 2 | 2 | Pasos antes de actualizar pesos |
| `learning_rate` | float | `1e-5` | `1e-4` | Tasa de aprendizaje |
| `warmup_steps` | int | 100 | 100 | Pasos de warm-up del scheduler |
| `weight_decay` | float | 0.01 | 0.01 | Regularización L2 |
| `use_peft` | bool | false | false | Activar LoRA (ahorra VRAM) |
| `peft_r` | int | 16 | 16 | Rango del adaptador LoRA |
| `peft_alpha` | int | 32 | 32 | Alpha de escalado LoRA |
| `whisper_language` | str | `"es"` | — | Idioma del target para Whisper |
| `whisper_task` | str | `"transcribe"` | — | Tarea: `"transcribe"` o `"translate"` |
| `fp16` | bool | auto | auto | Precisión mixta (solo si hay CUDA) |

---

### Responses del POST /entrenar/

#### 202 — Entrenamiento iniciado exitosamente

```json
{
  "mensaje": "Entrenamiento iniciado.",
  "experimento_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "num_muestras": 44,
  "estado_url": "/api/entrenamiento/experimentos/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c/estado/"
}
```

#### 400 — Ningún modo de selección especificado

```json
{
  "non_field_errors": [
    "Debes especificar al menos uno: \"todos\": true, \"sesiones\": [...], o \"comunidades\": [...]"
  ]
}
```

#### 404 — Lengua o modelo no existen en BD

```json
{ "error": "Lengua id=99 no existe." }
{ "error": "Modelo de audio id=99 no existe." }
```

#### 422 — Modelo no descargado en disco

```json
{
  "error": "El modelo \"openai/whisper-medium\" no está descargado. Descárgalo primero con POST /api/entrenamiento/modelos/descargar/"
}
```

#### 422 — Datos insuficientes (menos de 5 muestras etiquetadas)

```json
{
  "error": "Se necesitan al menos 5 muestras etiquetadas. Solo se encontraron 3. Etiqueta más audios antes de entrenar.",
  "muestras_encontradas": 3,
  "seleccion": {
    "modo": "sesiones",
    "sesiones": [{"comunidad": "kogui", "jornada": "grabacion_10_03_26_rituales"}]
  }
}
```

#### 409 — Ya hay un entrenamiento en curso

```json
{
  "error": "Ya hay un entrenamiento en curso para esta lengua y modelo."
}
```

---

### Qué hace el frontend con la respuesta 202

```javascript
// 1. Guardar en estado global
setState({
  experimentoActivo: {
    id: response.experimento_id,
    estado_url: response.estado_url,
    nombre: nombreFormulario,
  }
});

// 2. Navegar automáticamente al monitor
navigate(`/entrenamiento/monitor/${response.experimento_id}`);
```

---

## 7. Pantalla 5 — Monitor de entrenamiento (polling)

### Propósito
Mostrar el progreso del entrenamiento en tiempo real. Hace polling periódico hasta que el estado cambia a `"completado"` o `"fallido"`.

### Polling: GET Estado del experimento

```http
GET /api/entrenamiento/experimentos/{experimento_id}/estado/
```

```bash
# Reemplazar con el UUID del experimento recibido en el 202
curl http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c/estado/
```

### Response mientras entrena (estado: `"entrenando"`)

```json
{
  "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "nombre": "whisper-small-iku-fauna-v1",
  "lengua": "iku",
  "modelo": "openai/whisper-small",
  "estado": "entrenando",
  "is_active": false,
  "num_muestras_train": 38,
  "num_muestras_eval": 6,
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
```

### Response cuando termina (estado: `"completado"`)

```json
{
  "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "nombre": "whisper-small-iku-fauna-v1",
  "lengua": "iku",
  "modelo": "openai/whisper-small",
  "estado": "completado",
  "is_active": false,
  "num_muestras_train": 38,
  "num_muestras_eval": 6,
  "metricas": {
    "train_loss": 0.2134,
    "eval_loss": 0.3821,
    "eval_wer": 0.1820,
    "eval_cer": 0.0541,
    "total_steps": 190,
    "epochs": 15.0,
    "runtime_segundos": 2240.7
  },
  "mlflow_run_id": "abc123def456",
  "mlflow_experiment_name": "sayta-asr-iku",
  "task_info": null,
  "error_mensaje": "",
  "created_at": "2026-06-01T10:30:00Z",
  "completed_at": "2026-06-01T11:07:20Z"
}
```

### Response si falla (estado: `"fallido"`)

```json
{
  "estado": "fallido",
  "error_mensaje": "No se pudieron cargar muestras de audio. Error: [Errno 2] No such file or directory",
  "metricas": {},
  "task_info": null
}
```

### Lógica de polling en el frontend

```javascript
const POLL_INTERVAL_MS = 15000;  // 15 segundos

const startPolling = (experimentoId) => {
  const interval = setInterval(async () => {
    const data = await fetch(
      `/api/entrenamiento/experimentos/${experimentoId}/estado/`
    ).then(r => r.json());

    setEstado(data);

    if (data.estado === "completado") {
      clearInterval(interval);
      setMostrarBotonActivar(true);
    }

    if (data.estado === "fallido") {
      clearInterval(interval);
      setError(data.error_mensaje);
    }
  }, POLL_INTERVAL_MS);

  return interval;  // guardar para limpiar en cleanup
};

// Limpiar al desmontar:
useEffect(() => {
  const interval = startPolling(experimentoId);
  return () => clearInterval(interval);
}, [experimentoId]);
```

### Tabla de métricas y cómo mostrarlas

| Métrica | Descripción | Verde | Amarillo | Rojo |
|---|---|---|---|---|
| `eval_wer` | Word Error Rate — tasa de error por palabras | < 0.30 | 0.30–0.50 | > 0.50 |
| `eval_cer` | Character Error Rate — tasa de error por caracteres | < 0.15 | 0.15–0.30 | > 0.30 |
| `train_loss` | Pérdida de entrenamiento final | < 0.30 | 0.30–0.60 | > 0.60 |
| `eval_loss` | Pérdida en evaluación | < 0.40 | 0.40–0.70 | > 0.70 |

### Enlace a MLflow

```javascript
// Si mlflow_run_id está presente, construir URL:
const mlflowUrl = `http://mlflow-server:5000/#/experiments/${mlflow_experiment_id}/runs/${mlflow_run_id}`;
// O para local:
const mlflowUrl = `http://localhost:5000`;
```

---

## 8. Pantalla 6 — Historial de experimentos

### Propósito
Ver todos los experimentos de entrenamiento. Filtrar por lengua o estado. Comparar métricas entre versiones. Navegar al detalle.

### 8.1 — GET Lista de experimentos

```http
GET /api/entrenamiento/experimentos/
GET /api/entrenamiento/experimentos/?lengua_id=1
GET /api/entrenamiento/experimentos/?estado=completado
GET /api/entrenamiento/experimentos/?lengua_id=1&estado=completado
```

```bash
# Todos los experimentos
curl http://localhost:8000/api/entrenamiento/experimentos/

# Solo los de una lengua
curl "http://localhost:8000/api/entrenamiento/experimentos/?lengua_id=1"

# Solo los completados
curl "http://localhost:8000/api/entrenamiento/experimentos/?estado=completado"

# Combinado
curl "http://localhost:8000/api/entrenamiento/experimentos/?lengua_id=1&estado=completado"
```

#### Parámetros de filtro

| Parámetro | Tipo | Valores |
|---|---|---|
| `lengua_id` | int | ID de la lengua |
| `estado` | string | `pendiente`, `entrenando`, `completado`, `activo`, `fallido` |

#### Response 200

```json
{
  "total": 3,
  "experimentos": [
    {
      "id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
      "nombre": "whisper-small-iku-v2",
      "lengua_codigo": "iku",
      "lengua_nombre": "Arhuaco",
      "modelo_nombre": "openai/whisper-small",
      "comunidades_usadas": {
        "modo": "sesiones",
        "sesiones": [
          {"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"},
          {"comunidad": "arhuaco", "jornada": "grabacion_22_03_26_territorio"}
        ]
      },
      "estado": "activo",
      "estado_display": "Activo",
      "is_active": true,
      "num_muestras_train": 38,
      "num_muestras_eval": 6,
      "metricas": {
        "eval_wer": 0.1820,
        "eval_cer": 0.0541,
        "train_loss": 0.2134
      },
      "created_at": "2026-06-01T10:30:00Z",
      "completed_at": "2026-06-01T11:07:20Z"
    },
    {
      "id": "3a1b2c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
      "nombre": "whisper-small-iku-v1",
      "lengua_codigo": "iku",
      "lengua_nombre": "Arhuaco",
      "modelo_nombre": "openai/whisper-small",
      "comunidades_usadas": {
        "modo": "comunidades",
        "comunidades": ["arhuaco"]
      },
      "estado": "completado",
      "estado_display": "Completado",
      "is_active": false,
      "num_muestras_train": 48,
      "num_muestras_eval": 7,
      "metricas": {
        "eval_wer": 0.2910,
        "eval_cer": 0.0873,
        "train_loss": 0.3412
      },
      "created_at": "2026-05-28T09:00:00Z",
      "completed_at": "2026-05-28T10:12:44Z"
    },
    {
      "id": "8f9a0b1c-2d3e-4f5a-6b7c-8d9e0f1a2b3c",
      "nombre": "whisper-tiny-kogui-v1",
      "lengua_codigo": "kogui",
      "lengua_nombre": "Kogui",
      "modelo_nombre": "openai/whisper-tiny",
      "comunidades_usadas": {
        "modo": "todos"
      },
      "estado": "fallido",
      "estado_display": "Fallido",
      "is_active": false,
      "num_muestras_train": 0,
      "num_muestras_eval": 0,
      "metricas": {},
      "created_at": "2026-05-30T08:00:00Z",
      "completed_at": null
    }
  ]
}
```

---

### 8.2 — GET Detalle de un experimento

```http
GET /api/entrenamiento/experimentos/{uuid}/
```

```bash
curl http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c/
```

#### Response 200

```json
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
  "comunidades_usadas": {
    "modo": "sesiones",
    "sesiones": [
      {"comunidad": "arhuaco", "jornada": "grabacion_15_03_26_fauna"},
      {"comunidad": "arhuaco", "jornada": "grabacion_22_03_26_territorio"}
    ]
  },
  "estado": "activo",
  "estado_display": "Activo",
  "is_active": true,
  "config_entrenamiento": {
    "num_train_epochs": 15,
    "learning_rate": 1e-5,
    "per_device_train_batch_size": 4,
    "gradient_accumulation_steps": 2,
    "use_peft": false,
    "whisper_language": "es"
  },
  "ruta_modelo_entrenado": "/app/modelos_entrenados/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "mlflow_run_id": "abc123def456",
  "mlflow_experiment_id": "1",
  "mlflow_experiment_name": "sayta-asr-iku",
  "mlflow_tracking_uri": "/mnt/app_storage/mlruns",
  "metricas": {
    "train_loss": 0.2134,
    "eval_loss": 0.3821,
    "eval_wer": 0.1820,
    "eval_cer": 0.0541,
    "total_steps": 190,
    "epochs": 15.0,
    "runtime_segundos": 2240.7
  },
  "num_muestras_train": 38,
  "num_muestras_eval": 6,
  "error_mensaje": "",
  "task_id": "",
  "created_at": "2026-06-01T10:30:00Z",
  "completed_at": "2026-06-01T11:07:20Z"
}
```

---

## 9. Pantalla 7 — Activar modelo entrenado

### Propósito
Marcar un experimento completado como el modelo activo para su lengua. Después de esto, los endpoints de transcripción usarán este modelo automáticamente.

### POST Activar modelo

```http
POST /api/entrenamiento/experimentos/{uuid}/activar/
```

> No requiere body.

```bash
curl -X POST http://localhost:8000/api/entrenamiento/experimentos/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c/activar/
```

#### Response 200 — Activado exitosamente

```json
{
  "mensaje": "Modelo activado para lengua \"Arhuaco\".",
  "experimento_id": "7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "lengua": "iku",
  "ruta_modelo": "/app/modelos_entrenados/7f3e4c2a-1b5d-4a8e-9c3f-2d6b8e1a4f7c",
  "mlflow_run_id": "abc123def456"
}
```

#### Response 422 — Estado no permite activar

```json
{
  "error": "No se puede activar un experimento con estado \"entrenando\". Debe estar en estado \"completado\" o \"activo\"."
}
```

#### Response 422 — Modelo no existe en disco

```json
{
  "error": "La ruta del modelo entrenado no existe en disco."
}
```

#### Response 404 — Experimento no encontrado

```json
{
  "error": "Experimento no encontrado."
}
```

#### Qué hace el frontend después de activar

```javascript
// 1. Mostrar toast "Modelo activado para Arhuaco ✓"
showToast(`Modelo activado para ${response.lengua}`, "success");

// 2. Refrescar el panel de lenguas para actualizar el badge
await fetchLenguas();   // GET /api/entrenamiento/lenguas/

// 3. Habilitar los botones de transcripción para esa lengua
```

> **Nota:** Al activar un experimento, cualquier experimento previamente activo de la misma lengua pasa automáticamente a estado `"completado"`. Solo puede existir **un modelo activo por lengua** al mismo tiempo.

---

## 10. Pantalla 8 — Transcribir audio

### Propósito
Enviar un archivo de audio y recibir la transcripción usando el modelo ASR fine-tuneado activo para la lengua seleccionada.

### Prerrequisito
La lengua debe tener un experimento con `is_active: true` y `estado: "activo"`.

### POST Transcribir

```http
POST /api/entrenamiento/transcribir/
Content-Type: multipart/form-data
```

| Campo | Tipo | Descripción |
|---|---|---|
| `lengua_id` | int (form field) | ID de la lengua (de `GET /api/entrenamiento/lenguas/`) |
| `audio` | file | Archivo de audio |

#### Extensiones de audio permitidas

`.wav` · `.mp3` · `.ogg` · `.flac` · `.m4a` · `.mp4`

```bash
curl -X POST http://localhost:8000/api/entrenamiento/transcribir/ \
  -F "lengua_id=1" \
  -F "audio=@grabacion_saludos.wav"
```

#### Response 200 — Transcripción exitosa

```json
{
  "lengua": "iku",
  "modelo": "whisper-small-iku-v2",
  "transcripcion": "Du zari bunsi chano"
}
```

#### Response 422 — Sin modelo ASR activo para esa lengua

```json
{
  "error": "La lengua \"Arhuaco\" no tiene un modelo ASR activo. Entrena y activa un modelo con POST /api/entrenamiento/entrenar/ y POST /api/entrenamiento/experimentos/{id}/activar/"
}
```

#### Response 400 — Extensión de archivo no permitida

```json
{
  "error": "Extensión \".docx\" no permitida. Usa: .wav, .mp3, .ogg, .flac, .m4a, .mp4"
}
```

#### Response 500 — Error al procesar el audio

```json
{
  "error": "Error al transcribir: Audio file could not be read as PCM WAV, AIFF/AIFF-C, or Native FLAC"
}
```

#### Implementación en el frontend (multipart/form-data)

```javascript
const transcribir = async (lenguaId, audioFile) => {
  const formData = new FormData();
  formData.append("lengua_id", lenguaId.toString());
  formData.append("audio", audioFile);   // File object del input

  const response = await fetch("/api/entrenamiento/transcribir/", {
    method: "POST",
    body: formData,
    // NO establecer Content-Type — el browser lo pone automáticamente con el boundary
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error);
  }

  return await response.json();
  // { lengua, modelo, transcripcion }
};
```

---

## 11. Pantalla 9 — Pipeline completo audio → traducción

### Propósito
Pipeline de dos pasos en una sola llamada:
1. El audio se transcribe con el modelo ASR activo para la lengua.
2. El texto transcrito entra al buscador semántico (FAISS + embeddings) y se traduce al español.

### Prerrequisitos
- La lengua debe tener modelo ASR activo (`estado: "activo"`).
- La lengua debe tener una versión de embeddings activa (generada con `POST /api/terminos/embeddings/generar/`).

### POST Pipeline completo

```http
POST /api/entrenamiento/transcribir-y-traducir/
Content-Type: multipart/form-data
```

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `lengua_id` | int | — | ID de la lengua |
| `audio` | file | — | Archivo de audio |
| `direccion` | string | `"lengua_a_es"` | `"lengua_a_es"` o `"es_a_lengua"` |
| `top_k` | int | `3` | Número de resultados (1–10) |

```bash
curl -X POST http://localhost:8000/api/entrenamiento/transcribir-y-traducir/ \
  -F "lengua_id=1" \
  -F "audio=@grabacion.wav" \
  -F "direccion=lengua_a_es" \
  -F "top_k=3"
```

#### Response 200 — Pipeline completo exitoso

```json
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
```

#### Response 200 — Audio transcrito pero sin embedding activo (advertencia)

```json
{
  "lengua": "iku",
  "modelo_asr": "whisper-small-iku-v2",
  "transcripcion": "Du zari bunsi chano",
  "traduccion": {
    "advertencia": "La lengua \"Arhuaco\" no tiene embedding activo. Genera y activa uno con /api/terminos/embeddings/."
  }
}
```

> Cuando llega este caso, mostrar la transcripción con un aviso de que la traducción no está disponible, y ofrecer un enlace al módulo de embeddings.

---

## 12. Tabla resumen de todos los endpoints

| # | Método | Endpoint | Uso | Pantalla |
|---|---|---|---|---|
| 1 | GET | `/api/entrenamiento/lenguas/` | Estado de cada lengua y modelos ASR | P1 |
| 2 | GET | `/api/entrenamiento/modelos-disponibles/` | Catálogo con estado descargado | P2 |
| 3 | GET | `/api/entrenamiento/modelos/` | Modelos descargados en BD | P2, P4 |
| 4 | POST | `/api/entrenamiento/modelos/descargar/` | Descargar modelo de HF Hub | P2 |
| 5 | GET | `/api/entrenamiento/dataset/` | Resumen etiquetados por comunidad | P3 |
| 6 | GET | `/api/entrenamiento/dataset/sesiones/` | Lista plana de jornadas (checkboxes) | P3 |
| 7 | GET | `/api/entrenamiento/dataset/{community}/` | Detalle de jornadas de una comunidad | P3 |
| 8 | POST | `/api/entrenamiento/entrenar/` | Lanzar fine-tuning (3 modos) | P4 |
| 9 | GET | `/api/entrenamiento/experimentos/{id}/estado/` | Polling del estado | P5 |
| 10 | GET | `/api/entrenamiento/experimentos/` | Historial con filtros | P6 |
| 11 | GET | `/api/entrenamiento/experimentos/{id}/` | Detalle completo | P6 |
| 12 | POST | `/api/entrenamiento/experimentos/{id}/activar/` | Activar modelo para su lengua | P7 |
| 13 | POST | `/api/entrenamiento/transcribir/` | Audio → texto | P8 |
| 14 | POST | `/api/entrenamiento/transcribir-y-traducir/` | Audio → texto → traducción | P9 |

---

## 13. Catálogo de errores y cómo mostrarlos

| Código | Contexto | Mensaje típico | Acción en UI |
|---|---|---|---|
| `400` | POST /entrenar/ | `"Debes especificar al menos uno: todos, sesiones o comunidades"` | Toast rojo; mostrar qué campo falta |
| `400` | POST /transcribir/ | `"Extensión .docx no permitida"` | Toast rojo con extensiones válidas |
| `404` | POST /entrenar/ | `"Lengua id=99 no existe"` | Toast rojo; redirigir a P1 para reseleccionar lengua |
| `404` | POST /entrenar/ | `"Modelo de audio id=99 no existe"` | Toast rojo; redirigir a P2 |
| `404` | GET /dataset/{community}/ | `"Comunidad 'wiwa' no encontrada"` | 404 inline en la sección expandida |
| `404` | GET /experimentos/{id}/ | `"Experimento no encontrado"` | Página 404 o redirigir al historial |
| `409` | POST /entrenar/ | `"Ya hay un entrenamiento en curso"` | Toast naranja con enlace al monitor del experimento activo |
| `422` | POST /entrenar/ | `"Se necesitan al menos 5 muestras"` | Banner rojo debajo del contador de muestras; resaltar las sesiones insuficientes |
| `422` | POST /entrenar/ | `"El modelo no está descargado"` | Toast naranja con botón "Descargar modelo" que lleva a P2 |
| `422` | POST /transcribir/ | `"La lengua no tiene modelo ASR activo"` | Panel vacío con call-to-action "Entrenar modelo" → navegar a P4 |
| `422` | POST /transcribir/ | `"La transcripción resultó vacía"` | Toast amarillo "Audio sin voz detectable. Verifica la grabación" |
| `500` | POST /modelos/descargar/ | `"Repository not found on HuggingFace Hub"` | Modal de error con el nombre del repositorio y link a HF |
| `500` | POST /transcribir/ | `"Error al transcribir: ..."` | Toast rojo con el mensaje técnico en acordeón colapsable |

---

## Notas de implementación para el frontend

### Gestión de estado entre pantallas
Usar un store global (Zustand / Context / Redux) para `lenguaSeleccionada`, `modeloSeleccionado` y `seleccionDatos`. No pasar por query params — los UUIDs son largos y el estado de selección es complejo.

### Descarga de modelos
La llamada a `POST /modelos/descargar/` puede tardar hasta 10 minutos. Usar un modal con spinner que bloquee la UI y muestre el tamaño del modelo. Implementar un timeout de al menos 15 minutos en el cliente HTTP.

### Polling de estado
Implementar con `setInterval` y limpiar con `clearInterval` en el `useEffect` cleanup. Detener siempre cuando `estado == "completado"` o `estado == "fallido"`. Intervalo recomendado: **15 segundos**.

### Formulario multipart (transcripción)
No establecer `Content-Type` manualmente cuando se usa `FormData` — el browser lo pone automáticamente incluyendo el `boundary` necesario. Si se usa axios: `headers: { 'Content-Type': undefined }`.

### Contador de muestras seleccionadas
El total de muestras se calcula **en el cliente** sumando `etiquetados` de las jornadas seleccionadas. El botón "Lanzar entrenamiento" se habilita solo si `totalMuestras >= 5`. Este número se muestra en tiempo real mientras el usuario marca/desmarca checkboxes.

### `comunidades_usadas` en el historial
El campo `comunidades_usadas` en los experimentos tiene ahora estructura de objeto:
```json
{"modo": "todos"}
{"modo": "comunidades", "comunidades": ["arhuaco"]}
{"modo": "sesiones", "sesiones": [{"comunidad": "arhuaco", "jornada": "..."}]}
```
Renderizar un resumen legible: `"Todos los datos"`, `"Arhuaco, Kogui"`, o `"2 jornadas de Arhuaco, 1 de Kogui"`.
