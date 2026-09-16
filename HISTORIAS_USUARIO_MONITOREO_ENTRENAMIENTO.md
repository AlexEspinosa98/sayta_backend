# Historias de Usuario — Monitoreo y Control de Procesos de Entrenamiento
## Proyecto Sayta — Traductor de Lenguas Indígenas

> **Base URL:** `http://localhost:8000`
> **Prefijo:** `/api/entrenamiento/`
> **Motivación:** el 30/6/2026 el experimento `Traductor_iku_v2` quedó colgado en
> `estado="entrenando"` durante más de un día (proceso muerto, 0% GPU, sin logs)
> y solo se pudo diagnosticar entrando por SSH y corriendo `nvidia-smi`/`psql` a mano.
> Este documento diseña las piezas que faltan para hacerlo desde el panel.

---

## Estado de implementación

| Pieza | Estado | Notas |
|---|---|---|
| Marcar experimento colgado como fallido | ✅ **Ya existe** | `POST /experimentos/<id>/cancelar/` — si el hilo no está vivo, marca `fallido` directo |
| Liberar caché CUDA del proceso | ✅ **Ya existe** | `POST /sistema/liberar-memoria/` |
| Ver recursos del servidor (CPU/RAM/GPU) | ✅ **Ya existe** | `GET /sistema/` |
| Progreso en vivo (época/step/loss) | 🆕 Requiere implementación | No hay heartbeat persistente hoy — `task_info` vive solo en memoria y se pierde al reiniciar el proceso |
| Listado de procesos con salud (vivo/colgado) | 🆕 Requiere implementación | Hoy hay que cruzar `estado` de BD con SSH manual |
| Reiniciar el backend desde el panel | 🆕 Requiere implementación | Toca el proceso que atiende la propia request — diseño abajo |

---

## Épica 9 — Monitoreo y Control de Entrenamiento

### Permisos de acceso

| Acción | admin | desarrollador | investigador | anotador | consultor |
|---|:---:|:---:|:---:|:---:|:---:|
| Ver progreso / listado de procesos | ✅ | ✅ | ✅ | ✅ | ❌ |
| Marcar como fallido / cancelar | ✅ | ✅ | ✅ | ❌ | ❌ |
| Reiniciar backend | ✅ | ❌ | ❌ | ❌ | ❌ |

> Nota: hoy `DEFAULT_PERMISSION_CLASSES` está en `AllowAny` (`settings.py:113`, marcado
> `# TODO: volver a IsAuthenticated antes de producción`). Los ejemplos de abajo ya
> incluyen `Authorization: Token ...` asumiendo que ese TODO se resuelve antes de exponer
> `reiniciar-backend/` — ese endpoint en particular **no debería salir a producción sin permisos reales**.

---

### HU-MON-01 — Ver el progreso de época/step en tiempo real

**Como** investigador, **quiero** ver en qué época y step va un entrenamiento activo (con su loss),
**para** saber si avanza sin tener que entrar por SSH ni esperar a que termine.

**Criterios de aceptación:**
- Un nuevo modelo `EntrenamientoHeartbeat` (OneToOne con `ExperimentoEntrenamiento`) guarda el
  último estado conocido: `epoca_actual`, `epocas_totales`, `step_actual`, `steps_totales`,
  `loss_actual`, `fase` (`entrenando`/`evaluando`), `actualizado_en`.
- Un nuevo `TrainerCallback` (`_HeartbeatCallback`) escribe ese registro en `on_log` (cada
  `logging_steps=10`, ya configurado en `_build_training_args`) y en `on_epoch_end`/`on_evaluate`.
  No agrega escrituras nuevas por step — reutiliza la cadencia que ya existe.
- El endpoint calcula `segundos_desde_heartbeat` y `esta_vivo` (heartbeat en los últimos
  `N` segundos, default 180s = ~3× el intervalo esperado de log).
- Si el experimento nunca tuvo heartbeat (aún cargando el modelo/dataset) responde con
  `fase: "iniciando"` y `esta_vivo: null`.

**Endpoint:** `GET /api/entrenamiento/experimentos/<id>/progreso/` *(nuevo)*
**Autenticación requerida:** Sí — cualquier rol autenticado

```bash
curl http://localhost:8000/api/entrenamiento/experimentos/3385689f-a978-4f9e-9b33-4d319e08a5ee/progreso/ \
  -H "Authorization: Token <token>"

# Respuesta 200 — entrenamiento vivo
{
  "experimento_id": "3385689f-a978-4f9e-9b33-4d319e08a5ee",
  "nombre": "Traductor_iku_v2",
  "estado": "entrenando",
  "fase": "entrenando",
  "epoca_actual": 3.4,
  "epocas_totales": 30,
  "step_actual": 6210,
  "steps_totales": 57660,
  "porcentaje": 10.77,
  "loss_actual": 0.842,
  "ultimo_heartbeat": "2026-07-02T01:58:12Z",
  "segundos_desde_heartbeat": 42,
  "esta_vivo": true
}

# Respuesta 200 — entrenamiento colgado (el caso que vivimos)
{
  "experimento_id": "3385689f-a978-4f9e-9b33-4d319e08a5ee",
  "nombre": "Traductor_iku_v2",
  "estado": "entrenando",
  "fase": "entrenando",
  "epoca_actual": 0.0,
  "epocas_totales": 30,
  "step_actual": 0,
  "steps_totales": null,
  "porcentaje": 0.0,
  "loss_actual": null,
  "ultimo_heartbeat": null,
  "segundos_desde_heartbeat": null,
  "esta_vivo": false
}
```

---

### HU-MON-02 — Listar todos los procesos de entrenamiento con su estado de salud

**Como** investigador, **quiero** un botón "Ver procesos" que liste todos los entrenamientos
activos con una bandera clara de vivo/colgado, **para** detectar procesos pegados sin revisar
experimento por experimento.

**Criterios de aceptación:**
- Devuelve todos los experimentos con `estado="entrenando"`, ordenados por más antiguos primero
  (los más sospechosos de estar colgados aparecen arriba).
- Cada item trae el mismo resumen de progreso de HU-MON-01 más `colgado` (`true` si
  `esta_vivo=false` **y** `created_at` tiene más de 2 minutos, para no marcar como colgado algo
  que apenas está iniciando).
- Incluye `umbral_segundos` usado para el cálculo, para que el front pueda mostrarlo.
- El front pinta en rojo las filas con `colgado: true` y ahí muestra el botón de HU-MON-03.

**Endpoint:** `GET /api/entrenamiento/procesos/` *(nuevo)*
**Autenticación requerida:** Sí — cualquier rol autenticado

```bash
curl http://localhost:8000/api/entrenamiento/procesos/ \
  -H "Authorization: Token <token>"

# Respuesta 200
{
  "total": 1,
  "umbral_segundos": 180,
  "procesos": [
    {
      "experimento_id": "3385689f-a978-4f9e-9b33-4d319e08a5ee",
      "nombre": "Traductor_iku_v2",
      "lengua": "iku",
      "modelo": "openai/whisper-small",
      "epoca_actual": 0.0,
      "epocas_totales": 30,
      "porcentaje": 0.0,
      "ultimo_heartbeat": null,
      "segundos_desde_heartbeat": null,
      "esta_vivo": false,
      "colgado": true,
      "created_at": "2026-06-30T15:18:00Z"
    }
  ]
}

# Sin procesos activos
{ "total": 0, "umbral_segundos": 180, "procesos": [] }
```

---

### HU-MON-03 — Marcar un entrenamiento colgado como fallido (botón "Detener")

**Como** investigador, **quiero** un botón que detenga/marque como fallido un entrenamiento
colgado directamente desde el listado de procesos, **para** no depender de SSH ni de SQL manual.

**Ya implementado — no requiere código nuevo.** Solo se documenta aquí para dejar el contrato
claro de cara al front.

**Criterios de aceptación (comportamiento actual):**
- Si el hilo sigue vivo en memoria: le envía la señal de cancelación, el `Trainer` para al
  final del step/época actual (hasta ~30s) y el experimento queda `fallido` con
  `"Cancelado manualmente por el usuario"`.
- Si el hilo **no** está vivo (caso colgado tras un restart del backend, como el nuestro): marca
  el experimento como `fallido` de inmediato con `"Cancelado manualmente (hilo ya no activo)"`.
- Solo funciona si `estado == "entrenando"` — si ya está `completado`/`fallido` devuelve `409`.

**Endpoint:** `POST /api/entrenamiento/experimentos/<id>/cancelar/`
**Autenticación requerida:** Sí — rol `investigador`, `desarrollador` o `admin`

```bash
curl -X POST http://localhost:8000/api/entrenamiento/experimentos/3385689f-a978-4f9e-9b33-4d319e08a5ee/cancelar/ \
  -H "Authorization: Token <token>"

# Respuesta 200 — hilo colgado, marcado fallido directo (nuestro caso real)
{
  "mensaje": "Hilo no encontrado — experimento marcado como fallido directamente.",
  "experimento_id": "3385689f-a978-4f9e-9b33-4d319e08a5ee"
}

# Respuesta 409 — ya no está entrenando
{ "error": "El experimento tiene estado \"fallido\", no está en curso." }

# Respuesta 404
{ "error": "Experimento no encontrado." }
```

---

### HU-MON-04 — Reiniciar el backend desde el panel de administración

**Como** administrador, **quiero** un botón que reinicie el backend cuando detecto GPU/RAM
retenida que `liberar-memoria/` no logra limpiar, **para** no depender de acceso SSH al servidor.

**Criterios de aceptación:**
- Solo rol `admin` (acción destructiva: corta todas las conexiones activas por unos segundos).
- El endpoint responde `202 Accepted` **antes** de que el proceso muera, para no dejar la
  request colgada esperando una respuesta que nunca llega.
- Internamente: agenda con `threading.Timer(2.0, ...)` el envío de `SIGTERM` al proceso maestro
  de Gunicorn (`os.kill(1, signal.SIGTERM)` — el master corre como PID 1 dentro del contenedor,
  ver `Dockerfile`/`entrypoint.sh`). El shutdown de Gunicorn es limpio; Docker lo revive por la
  política `restart: unless-stopped` del `docker-compose.yml`.
- El front debe pedir confirmación explícita ("esto va a desconectar a todos los usuarios por
  ~10-20s") antes de llamar este endpoint.
- Requiere que el experimento colgado ya haya sido marcado `fallido` (HU-MON-03) — reiniciar el
  backend **no** limpia el `estado` en BD por sí solo, solo libera memoria/hilos zombis.

**Endpoint:** `POST /api/entrenamiento/sistema/reiniciar-backend/` *(nuevo)*
**Autenticación requerida:** Sí — solo rol `admin`

```bash
curl -X POST http://localhost:8000/api/entrenamiento/sistema/reiniciar-backend/ \
  -H "Authorization: Token <token-del-admin>"

# Respuesta 202
{
  "mensaje": "Reinicio solicitado. El backend se detendrá en ~2s y Docker lo reiniciará automáticamente (restart: unless-stopped). Espera ~30-60s antes de reintentar peticiones."
}

# Con token que no es admin → 403
{ "detail": "Se requiere rol de Administrador." }
```

---

### HU-MON-05 — Modelo de datos dedicado para el heartbeat de entrenamiento

**Como** desarrollador del sistema, **quiero** un modelo separado de `ExperimentoEntrenamiento`
para guardar el heartbeat, **para** no mezclar el estado transaccional del experimento (que se
actualiza pocas veces) con escrituras frecuentes de progreso.

**Criterios de aceptación:**
- Un solo registro por experimento (`OneToOneField`, se sobrescribe con `update_or_create` en
  cada heartbeat) — no crece sin límite; el histórico de métricas por step ya vive en MLflow.
- Migración nueva en `entrenamiento/migrations/`.
- Se expone únicamente a través de HU-MON-01/02 — no tiene endpoint propio de escritura (solo el
  callback del `Trainer`, que corre en el mismo proceso, escribe directo con el ORM).

```python
# entrenamiento/models.py — modelo nuevo
class EntrenamientoHeartbeat(models.Model):
    experimento = models.OneToOneField(
        ExperimentoEntrenamiento,
        on_delete=models.CASCADE,
        related_name='heartbeat',
        primary_key=True,
    )
    fase = models.CharField(max_length=20, default='iniciando')  # iniciando|entrenando|evaluando
    epoca_actual = models.FloatField(default=0)
    epocas_totales = models.IntegerField(default=0)
    step_actual = models.IntegerField(default=0)
    steps_totales = models.IntegerField(null=True, blank=True)
    loss_actual = models.FloatField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)
```

---

## Tabla resumen de endpoints — Monitoreo de Entrenamiento

| # | Método | Endpoint | Estado | Roles | Descripción |
|---|---|---|---|---|---|
| 1 | GET | `/api/entrenamiento/experimentos/<id>/progreso/` | 🆕 nuevo | Todos | Época/step/loss en vivo + `esta_vivo` |
| 2 | GET | `/api/entrenamiento/procesos/` | 🆕 nuevo | Todos | Lista de entrenamientos activos con salud |
| 3 | POST | `/api/entrenamiento/experimentos/<id>/cancelar/` | ✅ existente | `investigador`+ | Detener / marcar como fallido |
| 4 | POST | `/api/entrenamiento/sistema/reiniciar-backend/` | 🆕 nuevo | `admin` | Reinicia el proceso del backend |
| 5 | POST | `/api/entrenamiento/sistema/liberar-memoria/` | ✅ existente | `investigador`+ | Libera caché CUDA/modelos sin reiniciar |
| 6 | GET | `/api/entrenamiento/sistema/` | ✅ existente | Todos | CPU/RAM/GPU del servidor |

---

## Flujo recomendado en el front

```
1. Panel "Procesos de entrenamiento" (botón nuevo en el nav)
   GET /api/entrenamiento/procesos/
   → tabla con barra de progreso (época/epocas_totales) por fila
   → fila en rojo si colgado=true

2. Si colgado=true, mostrar botón "Detener"
   POST /api/entrenamiento/experimentos/<id>/cancelar/
   → refrescar la tabla, la fila desaparece (ya no está "entrenando")

3. Si después de detener sigue reteniendo GPU (revisar GET /sistema/)
   POST /api/entrenamiento/sistema/liberar-memoria/

4. Si ni así se libera memoria (última opción, solo admin)
   POST /api/entrenamiento/sistema/reiniciar-backend/
   → esperar ~30-60s, luego GET /sistema/ para confirmar
```

---

## Notas técnicas

| Aspecto | Detalle |
|---|---|
| Por qué OneToOne y no historial completo | El histórico de métricas por step ya se loguea en MLflow (`_MLflowEpochCallback`) — duplicar eso en Postgres sería redundante |
| Cadencia de escritura | Reutiliza `logging_steps=10` ya configurado — no agrega overhead de escritura nuevo |
| `esta_vivo` vs `colgado` | `esta_vivo` es puntual (heartbeat reciente); `colgado` en el listado añade un margen de gracia de 2 min para no marcar como colgado algo que apenas arrancó |
| Reinicio del backend | Señal a PID 1, no `docker restart` desde dentro del contenedor — evita depender de montar `/var/run/docker.sock` (riesgo de seguridad mayor: acceso al socket de Docker equivale a root en el host) |
| Migraciones | `EntrenamientoHeartbeat` requiere `python manage.py makemigrations entrenamiento && migrate` antes de desplegar |
