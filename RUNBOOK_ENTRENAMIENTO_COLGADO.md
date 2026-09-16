# Runbook: Entrenamiento colgado (hilo pegado)

Contexto: el entrenamiento corre como `threading.Thread(daemon=True)` dentro de
un worker de Gunicorn en el contenedor `sayta-backend`. No hay heartbeat ni
`is_alive()`, así que si el hilo muere o se cuelga, la BD puede quedar
mostrando `estado = "entrenando"` indefinidamente
(`entrenamiento/services/training_service.py`, `entrenamiento/views.py:777`).

Ejecutar todo esto por SSH en el servidor donde corre el `docker-compose.yml`.

---

## 1. Diagnóstico — confirmar que está pegado

```bash
# 1.1 Estado y uptime del contenedor
docker ps --filter name=sayta-backend --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"

# 1.2 CPU de los workers de Gunicorn (correr dos veces con ~2 min de diferencia)
docker top sayta-backend -eo pid,ppid,cmd,%cpu,etime

# 1.3 Procesos GPU — debe listar un proceso python si hay entrenamiento activo
docker exec sayta-backend nvidia-smi

# 1.4 Logs recientes — buscar progreso (steps/epochs) o SIGKILL/timeout de Gunicorn
docker logs --since 15m sayta-backend | tail -100

# 1.5 Archivos nuevos en disco (bind mount, se puede leer directo desde el host)
find /mnt/sayta_data/data/app_storage -newermt '-10 minutes' -type f
find /mnt/sayta_data/models -newermt '-10 minutes' -type f
```

Si (1.2) no crece, (1.3) no muestra proceso python, (1.4) no tiene líneas
nuevas y (1.5) no devuelve archivos → el hilo está muerto/colgado.

---

## 2. Ver qué experimento quedó colgado

```bash
docker exec -it sayta-db bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, nombre, estado, task_id, created_at FROM experimentos_entrenamiento WHERE estado = '\''entrenando'\'';"'
```

Anota el `id` (UUID) del experimento colgado — lo necesitas en el paso 4.

---

## 3. Detener el entrenamiento

### Opción A — Quirúrgica (recomendada primero)

Mata solo el worker de Gunicorn que tiene el hilo colgado; el master de
Gunicorn levanta uno nuevo automáticamente y libera la GPU sin tumbar el
contenedor completo.

```bash
# 3.1 Ubicar el PID del worker (columna PID de docker top, paso 1.2)
docker exec sayta-backend ps aux | grep -i gunicorn

# 3.2 Matarlo (reemplaza <PID> por el que identificaste)
docker exec sayta-backend kill -9 <PID>

# 3.3 Verificar que el master levantó un worker nuevo
docker exec sayta-backend ps aux | grep -i gunicorn
```

### Opción B — Reinicio completo del backend (si A no libera la GPU)

Más disruptivo: corta todas las conexiones activas al backend por unos
segundos, pero garantiza liberar memoria de GPU y matar cualquier hilo
zombi.

```bash
# 3.4 Ir al directorio donde está el docker-compose.yml
cd /ruta/al/proyecto/sayta

# 3.5 Reiniciar solo el servicio backend
docker compose restart backend

# 3.6 Seguir el arranque hasta que pase el healthcheck
docker compose logs -f backend
```

---

## 4. Verificar que la GPU quedó libre

```bash
docker exec sayta-backend nvidia-smi
```

La sección `Processes` no debe listar ningún proceso python huérfano.

---

## 5. Limpiar el estado en la BD

El thread muerto no actualiza el `estado` del experimento, así que hay que
marcarlo manualmente como fallido (reemplaza `<ID_DEL_EXPERIMENTO>` por el
UUID del paso 2).

```bash
docker exec -it sayta-db bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE experimentos_entrenamiento SET estado='\''fallido'\'', error_mensaje='\''Entrenamiento detenido manualmente: hilo colgado sin heartbeat'\'', completed_at=NOW() WHERE id='\''<ID_DEL_EXPERIMENTO>'\'';"'
```

Alternativa vía Django shell (si prefieres no tocar SQL a mano):

```bash
docker exec -it sayta-backend python manage.py shell -c "
from entrenamiento.models import ExperimentoEntrenamiento
exp = ExperimentoEntrenamiento.objects.get(id='<ID_DEL_EXPERIMENTO>')
exp.estado = ExperimentoEntrenamiento.ESTADO_FALLIDO
exp.error_mensaje = 'Entrenamiento detenido manualmente: hilo colgado sin heartbeat'
from django.utils import timezone
exp.completed_at = timezone.now()
exp.save()
"
```

---

## 6. Verificación final

```bash
# 6.1 Confirmar que ya no queda ningún experimento en "entrenando"
docker exec -it sayta-db bash -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, nombre, estado FROM experimentos_entrenamiento WHERE estado = '\''entrenando'\'';"'

# 6.2 Confirmar salud del backend
curl -f http://localhost:8000/health/ || echo "backend no responde"
```

Si (6.1) devuelve vacío y (6.2) responde OK, el sistema quedó limpio para
lanzar un nuevo entrenamiento.
