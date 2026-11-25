"""
Worker de entrenamiento: toma trabajos de la cola (TrabajoEntrenamiento) y los ejecuta uno a uno.
Corre en el contenedor sayta-trainer; la web solo encola (SAYTA_TRAINING_WORKER_MODE=1).

  python manage.py entrenar_worker            # bucle infinito
  python manage.py entrenar_worker --una-vez  # ejecuta un trabajo (si lo hay) y sale
"""
import logging
import socket
import threading
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ejecuta los entrenamientos encolados (contenedor sayta-trainer).'

    def add_arguments(self, parser):
        parser.add_argument('--una-vez', action='store_true')
        parser.add_argument('--espera', type=int, default=5, help='Segundos entre consultas a la cola')

    def handle(self, *args, **o):
        from entrenamiento.models import ExperimentoEntrenamiento, TrabajoEntrenamiento
        from entrenamiento.services import training_service

        worker = socket.gethostname()
        # Trabajos que quedaron «ejecutando» de un worker anterior (reinicio): no se pueden reanudar.
        huerfanos = TrabajoEntrenamiento.objects.filter(estado__in=[TrabajoEntrenamiento.EJECUTANDO, TrabajoEntrenamiento.CANCELAR])
        for job in huerfanos:
            job.estado = TrabajoEntrenamiento.FALLIDO
            job.mensaje = 'El worker se reinició durante el entrenamiento'
            job.terminado_en = timezone.now()
            job.save(update_fields=['estado', 'mensaje', 'terminado_en'])
            ExperimentoEntrenamiento.objects.filter(pk=job.experimento_id, estado=ExperimentoEntrenamiento.ESTADO_ENTRENANDO).update(
                estado=ExperimentoEntrenamiento.ESTADO_FALLIDO, error_mensaje='El worker de entrenamiento se reinició durante el entrenamiento', completed_at=timezone.now())
        if huerfanos:
            self.stdout.write(f'{len(huerfanos)} trabajo(s) huérfano(s) marcados como fallidos')
        self.stdout.write(f'Worker {worker} esperando trabajos…')

        while True:
            job = None
            with transaction.atomic():
                job = (TrabajoEntrenamiento.objects.select_for_update(skip_locked=True)
                       .filter(estado=TrabajoEntrenamiento.EN_COLA).order_by('creado_en').first())
                if job:
                    job.estado = TrabajoEntrenamiento.EJECUTANDO
                    job.worker = worker
                    job.iniciado_en = timezone.now()
                    job.save(update_fields=['estado', 'worker', 'iniciado_en'])
            if job is None:
                connection.close()
                if o['una_vez']:
                    return
                time.sleep(o['espera'])
                continue

            self.stdout.write(f'Iniciando trabajo {job.id} (experimento {job.experimento_id})')
            stop_event = threading.Event()
            fin = threading.Event()

            def vigilar(job_id=str(job.id)):
                # Atiende la solicitud de cancelación escrita en BD por la web.
                while not fin.wait(5):
                    try:
                        estado = TrabajoEntrenamiento.objects.filter(pk=job_id).values_list('estado', flat=True).first()
                    except Exception:
                        continue
                    if estado == TrabajoEntrenamiento.CANCELAR:
                        stop_event.set()
                        return

            threading.Thread(target=vigilar, daemon=True, name='vigilante-cancelacion').start()
            with training_service._tasks_lock:
                training_service._active_tasks[str(job.id)] = {'experimento_id': str(job.experimento_id), 'started_at': timezone.now().isoformat(), 'estado': 'entrenando'}
                training_service._stop_events[str(job.id)] = stop_event
            try:
                training_service._force_single_process_training_env()
                training_service._training_thread(str(job.experimento_id), job.samples, job.config, str(job.id), stop_event)
            except Exception as exc:  # _training_thread ya captura todo; esto es por si acaso
                logger.exception('Trabajo %s: error inesperado: %s', job.id, exc)
            finally:
                fin.set()
                with training_service._tasks_lock:
                    training_service._active_tasks.pop(str(job.id), None)
                    training_service._stop_events.pop(str(job.id), None)

            job.refresh_from_db()
            exp_estado = ExperimentoEntrenamiento.objects.filter(pk=job.experimento_id).values_list('estado', flat=True).first()
            if stop_event.is_set():
                job.estado = TrabajoEntrenamiento.CANCELADO
            elif exp_estado == ExperimentoEntrenamiento.ESTADO_COMPLETADO:
                job.estado = TrabajoEntrenamiento.TERMINADO
            else:
                job.estado = TrabajoEntrenamiento.FALLIDO
            job.samples = []   # ya no hacen falta; libera espacio en BD
            job.terminado_en = timezone.now()
            job.save(update_fields=['estado', 'samples', 'terminado_en'])
            self.stdout.write(f'Trabajo {job.id} → {job.estado}')
            connection.close()
            if o['una_vez']:
                return
