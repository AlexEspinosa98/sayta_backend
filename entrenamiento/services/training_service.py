"""
Servicio de fine-tuning de modelos ASR (Wav2Vec2 / Whisper).

Flujo completo:
  1. Cargar muestras etiquetadas (audio + transcripción)
  2. Construir HuggingFace Dataset con split train/eval (90/10)
  3. Preprocesar: resamplear a 16kHz, extraer features
  4. Wav2Vec2: construir vocabulario CTC desde los textos de entrenamiento
  5. Fine-tune con Trainer / Seq2SeqTrainer
  6. Loggear métricas por época en MLflow (WER, CER, loss)
  7. Guardar el mejor modelo en disco
  8. Actualizar ExperimentoEntrenamiento en BD

Config admitida (todos opcionales, con valores por defecto):
  num_train_epochs        int   = 20
  per_device_train_batch  int   = 4
  per_device_eval_batch   int   = 4
  learning_rate           float = 1e-4
  weight_decay            float = 0.005
  warmup_steps            int   = 100
  gradient_accumulation   int   = 2
  fp16                    bool  = auto (True si hay CUDA)
  use_peft                bool  = False
  peft_r                  int   = 16
  peft_alpha              int   = 32
  peft_dropout            float = 0.05
  mlflow_tracking_uri     str   = settings.MLFLOW_TRACKING_URI
  whisper_language        str   = 'es'
  whisper_task            str   = 'transcribe'
"""

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

_active_tasks: Dict[str, Dict] = {}
_tasks_lock = threading.Lock()


# ==================================================================
# Punto de entrada público
# ==================================================================

def launch_training(experimento_id: str, samples: List[Dict], config: Dict) -> str:
    """Lanza el entrenamiento en un hilo daemon. Retorna task_id."""
    task_id = str(uuid.uuid4())
    t = threading.Thread(
        target=_training_thread,
        args=(experimento_id, samples, config, task_id),
        daemon=True,
        name=f'train_{experimento_id[:8]}',
    )
    with _tasks_lock:
        _active_tasks[task_id] = {
            'experimento_id': experimento_id,
            'started_at': datetime.now().isoformat(),
            'estado': 'iniciando',
        }
    t.start()
    return task_id


def get_task_info(task_id: str) -> Optional[Dict]:
    with _tasks_lock:
        return _active_tasks.get(task_id)


# ==================================================================
# Hilo de entrenamiento
# ==================================================================

def _training_thread(experimento_id: str, samples: List[Dict], config: Dict, task_id: str):
    from django.db import connection
    from django.utils import timezone
    from entrenamiento.models import ExperimentoEntrenamiento

    exp = None
    try:
        exp = ExperimentoEntrenamiento.objects.get(id=experimento_id)
        exp.estado = ExperimentoEntrenamiento.ESTADO_ENTRENANDO
        exp.task_id = task_id
        exp.save(update_fields=['estado', 'task_id'])

        with _tasks_lock:
            if task_id in _active_tasks:
                _active_tasks[task_id]['estado'] = 'entrenando'

        metricas, output_dir, run_id, exp_id, exp_name, tracking_uri = _run_training(
            exp, samples, config, task_id
        )

        exp.refresh_from_db()
        exp.estado = ExperimentoEntrenamiento.ESTADO_COMPLETADO
        exp.metricas = metricas
        exp.ruta_modelo_entrenado = output_dir
        exp.mlflow_run_id = run_id
        exp.mlflow_experiment_id = exp_id
        exp.mlflow_experiment_name = exp_name
        exp.mlflow_tracking_uri = tracking_uri
        exp.completed_at = timezone.now()
        exp.error_mensaje = ''
        exp.save()
        logger.info('Entrenamiento completado: %s', experimento_id)

    except Exception as exc:
        logger.error('Error en entrenamiento %s: %s', experimento_id, exc, exc_info=True)
        try:
            if exp is None:
                exp = ExperimentoEntrenamiento.objects.get(id=experimento_id)
            exp.estado = ExperimentoEntrenamiento.ESTADO_FALLIDO
            exp.error_mensaje = str(exc)
            from django.utils import timezone as tz
            exp.completed_at = tz.now()
            exp.save(update_fields=['estado', 'error_mensaje', 'completed_at'])
        except Exception:
            pass
    finally:
        with _tasks_lock:
            _active_tasks.pop(task_id, None)
        try:
            connection.close()
        except Exception:
            pass


# ==================================================================
# Core de entrenamiento
# ==================================================================

def _run_training(exp, samples: List[Dict], config: Dict, task_id: str):
    """
    Ejecuta el fine-tuning completo. Retorna
    (metricas, output_dir, mlflow_run_id, mlflow_exp_id, mlflow_exp_name, tracking_uri).
    """
    _check_deps()

    import mlflow
    import torch
    from django.conf import settings

    tipo = exp.modelo_base.tipo
    modelo_hf = exp.modelo_base.nombre_hf
    ruta_local = exp.modelo_base.ruta_local

    # --- MLflow setup ---
    tracking_uri = config.get(
        'mlflow_tracking_uri',
        getattr(settings, 'MLFLOW_TRACKING_URI', str(Path(settings.BASE_DIR) / 'mlruns')),
    )
    mlflow.set_tracking_uri(tracking_uri)
    experiment_name = f'sayta-asr-{exp.lengua.codigo}'
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=exp.nombre) as run:
        run_id = run.info.run_id
        exp_id = run.info.experiment_id

        # --- Log hiperparámetros ---
        mlflow.log_params({
            'modelo_base': modelo_hf,
            'tipo_modelo': tipo,
            'lengua': exp.lengua.codigo,
            'comunidades': ','.join(exp.comunidades_usadas),
            'num_muestras_total': len(samples),
            'epochs': config.get('num_train_epochs', 20),
            'learning_rate': config.get('learning_rate', 1e-4),
            'batch_size': config.get('per_device_train_batch_size', 4),
            'gradient_accumulation': config.get('gradient_accumulation_steps', 2),
            'warmup_steps': config.get('warmup_steps', 100),
            'weight_decay': config.get('weight_decay', 0.005),
            'use_peft': config.get('use_peft', False),
        })

        # --- Cargar modelo y procesador ---
        model, processor = _load_model_for_training(tipo, modelo_hf, ruta_local, samples, config)

        # --- Construir dataset HF ---
        train_ds, eval_ds = _build_hf_dataset(samples, processor, tipo, config)

        exp.num_muestras_train = len(train_ds)
        exp.num_muestras_eval = len(eval_ds)
        exp.save(update_fields=['num_muestras_train', 'num_muestras_eval'])

        mlflow.log_params({
            'num_train': len(train_ds),
            'num_eval': len(eval_ds),
        })

        # --- Data collator ---
        data_collator = _build_collator(tipo, processor, model)

        # --- Función de métricas ---
        compute_metrics_fn = _build_compute_metrics(processor, tipo)

        # --- Output dir ---
        output_dir = str(
            Path(getattr(settings, 'MODELOS_ENTRENADOS_DIR', str(Path(settings.BASE_DIR) / 'modelos_entrenados')))
            / str(exp.id)
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # --- Training arguments ---
        use_fp16 = config.get('fp16', torch.cuda.is_available())
        training_args = _build_training_args(tipo, output_dir, config, use_fp16)

        # --- PEFT / LoRA opcional ---
        if config.get('use_peft', False):
            model = _apply_peft(model, tipo, config)

        # --- Callback MLflow por época ---
        mlflow_callback = _MLflowEpochCallback()

        # --- Trainer ---
        TrainerClass, extra_kwargs = _get_trainer_class(tipo)
        trainer = TrainerClass(
            model=model,
            args=training_args,
            compute_metrics=compute_metrics_fn,
            train_dataset=train_ds,
            eval_dataset=eval_ds,
            data_collator=data_collator,
            callbacks=[mlflow_callback],
            **extra_kwargs,
        )

        # --- Entrenamiento ---
        logger.info('Iniciando entrenamiento: %d train / %d eval', len(train_ds), len(eval_ds))
        train_result = trainer.train()

        # --- Guardar modelo final ---
        trainer.save_model(output_dir)
        if hasattr(processor, 'save_pretrained'):
            processor.save_pretrained(output_dir)

        # --- Evaluación final ---
        eval_results = trainer.evaluate()

        # --- Métricas finales ---
        metricas = {
            'train_loss': round(train_result.training_loss, 4),
            'eval_loss': round(eval_results.get('eval_loss', 0), 4),
            'eval_wer': round(eval_results.get('eval_wer', 1.0), 4),
            'eval_cer': round(eval_results.get('eval_cer', 1.0), 4),
            'total_steps': train_result.global_step,
            'epochs': training_args.num_train_epochs,
            'runtime_segundos': round(eval_results.get('eval_runtime', 0), 1),
        }
        mlflow.log_metrics({k: v for k, v in metricas.items() if isinstance(v, (int, float))})

        # Guardar config de entrenamiento como artefacto
        config_path = Path(output_dir) / 'training_config.json'
        config_path.write_text(json.dumps(config, indent=2, default=str), encoding='utf-8')
        mlflow.log_artifact(str(config_path))

        logger.info('Métricas finales: %s', metricas)
        return metricas, output_dir, run_id, exp_id, experiment_name, tracking_uri


# ==================================================================
# Helpers de entrenamiento
# ==================================================================

def _check_deps():
    missing = []
    for pkg in ('transformers', 'datasets', 'evaluate', 'mlflow', 'librosa', 'soundfile', 'jiwer'):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        raise RuntimeError(
            f'Dependencias faltantes: {", ".join(missing)}. '
            f'Instala con: pip install {" ".join(missing)}'
        )


def _load_model_for_training(tipo: str, modelo_hf: str, ruta_local: str, samples: List[Dict], config: Dict):
    """Carga modelo y construye procesador listo para entrenamiento."""
    src = ruta_local if ruta_local else modelo_hf

    if tipo == 'whisper':
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        language = config.get('whisper_language', 'es')
        task = config.get('whisper_task', 'transcribe')
        processor = WhisperProcessor.from_pretrained(src, language=language, task=task)
        model = WhisperForConditionalGeneration.from_pretrained(src)
        model.generation_config.language = language
        model.generation_config.task = task
        model.generation_config.forced_decoder_ids = None
        return model, processor

    else:  # wav2vec2 CTC
        from transformers import (
            Wav2Vec2CTCTokenizer,
            Wav2Vec2FeatureExtractor,
            Wav2Vec2ForCTC,
            Wav2Vec2Processor,
        )
        import tempfile

        # Construir vocabulario desde los textos de entrenamiento
        all_chars = set()
        for s in samples:
            all_chars.update(list(s['sentence'].lower()))
        all_chars = sorted(all_chars - {' '})

        vocab = {'[PAD]': 0, '[UNK]': 1, '|': 2}
        for idx, ch in enumerate(all_chars, start=3):
            vocab[ch] = idx

        with tempfile.TemporaryDirectory() as tmpdir:
            vocab_path = Path(tmpdir) / 'vocab.json'
            vocab_path.write_text(json.dumps(vocab, ensure_ascii=False), encoding='utf-8')
            tokenizer = Wav2Vec2CTCTokenizer(
                str(vocab_path),
                unk_token='[UNK]',
                pad_token='[PAD]',
                word_delimiter_token='|',
            )

        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(src)
        processor = Wav2Vec2Processor(feature_extractor=feature_extractor, tokenizer=tokenizer)

        model = Wav2Vec2ForCTC.from_pretrained(
            src,
            attention_dropout=config.get('attention_dropout', 0.1),
            hidden_dropout=config.get('hidden_dropout', 0.1),
            feat_proj_dropout=config.get('feat_proj_dropout', 0.0),
            mask_time_prob=config.get('mask_time_prob', 0.05),
            layerdrop=config.get('layerdrop', 0.1),
            ctc_loss_reduction='mean',
            pad_token_id=processor.tokenizer.pad_token_id,
            vocab_size=len(processor.tokenizer),
            ignore_mismatched_sizes=True,
        )
        # Congelar extractor de características (mejor para fine-tuning con pocos datos)
        model.freeze_feature_extractor()
        return model, processor


def _load_audio_16k(audio_path: str):
    """Carga y resamplea audio a 16kHz. Retorna numpy array."""
    import librosa
    speech, _ = librosa.load(audio_path, sr=16000, mono=True)
    return speech


def _build_hf_dataset(samples: List[Dict], processor, tipo: str, config: Dict):
    """Construye HF Dataset preprocesado y hace split train/eval."""
    import datasets as hf_datasets

    raw_data = {'audio': [], 'sentence': []}
    skipped = 0
    for s in samples:
        try:
            speech = _load_audio_16k(s['audio'])
            raw_data['audio'].append(speech)
            raw_data['sentence'].append(s['sentence'])
        except Exception as e:
            logger.warning('Audio no cargado %s: %s', s['audio'], e)
            skipped += 1

    if skipped:
        logger.warning('%d audios descartados por error de carga', skipped)

    if not raw_data['audio']:
        raise RuntimeError('No se pudieron cargar muestras de audio. Verifica los archivos.')

    dataset = hf_datasets.Dataset.from_dict(raw_data)
    split = dataset.train_test_split(test_size=0.1, seed=42)
    train_ds = split['train']
    eval_ds = split['test']

    if tipo == 'whisper':
        def preprocess_whisper(batch):
            features = processor(
                batch['audio'], sampling_rate=16000, return_tensors='np'
            ).input_features[0]
            labels = processor.tokenizer(batch['sentence']).input_ids
            return {'input_features': features, 'labels': labels}

        train_ds = train_ds.map(preprocess_whisper, remove_columns=['audio', 'sentence'])
        eval_ds = eval_ds.map(preprocess_whisper, remove_columns=['audio', 'sentence'])
    else:
        def preprocess_wav2vec2(batch):
            inputs = processor(batch['audio'], sampling_rate=16000)
            with processor.as_target_processor():
                labels = processor(batch['sentence'])
            return {
                'input_values': inputs.input_values[0],
                'labels': labels.input_ids,
            }

        train_ds = train_ds.map(preprocess_wav2vec2, remove_columns=['audio', 'sentence'])
        eval_ds = eval_ds.map(preprocess_wav2vec2, remove_columns=['audio', 'sentence'])

    return train_ds, eval_ds


@dataclass
class _DataCollatorCTC:
    """Data collator para Wav2Vec2 CTC con padding dinámico."""
    processor: Any
    padding: Union[bool, str] = True

    def __call__(self, features: List[Dict]) -> Dict[str, Any]:
        import torch
        input_features = [{'input_values': f['input_values']} for f in features]
        label_features = [{'input_ids': f['labels']} for f in features]

        batch = self.processor.pad(input_features, padding=self.padding, return_tensors='pt')
        with self.processor.as_target_processor():
            labels_batch = self.processor.pad(label_features, padding=self.padding, return_tensors='pt')
        labels = labels_batch['input_ids'].masked_fill(labels_batch.attention_mask.ne(1), -100)
        batch['labels'] = labels
        return batch


@dataclass
class _DataCollatorWhisper:
    """Data collator para Whisper Seq2Seq."""
    processor: Any
    decoder_start_token_id: int

    def __call__(self, features: List[Dict]) -> Dict[str, Any]:
        import torch
        input_features = [{'input_features': f['input_features']} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors='pt')

        label_features = [{'input_ids': f['labels']} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors='pt')
        labels = labels_batch['input_ids'].masked_fill(labels_batch.attention_mask.ne(1), -100)

        if (labels[:, 0] == self.decoder_start_token_id).all().cpu().item():
            labels = labels[:, 1:]
        batch['labels'] = labels
        return batch


def _build_collator(tipo: str, processor, model):
    if tipo == 'whisper':
        return _DataCollatorWhisper(
            processor=processor,
            decoder_start_token_id=model.config.decoder_start_token_id,
        )
    return _DataCollatorCTC(processor=processor, padding=True)


def _build_compute_metrics(processor, tipo: str):
    import evaluate
    wer_metric = evaluate.load('wer')
    cer_metric = evaluate.load('cer')

    def compute_metrics(pred):
        import numpy as np
        pred_ids = np.argmax(pred.predictions, axis=-1) if tipo == 'wav2vec2' else pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

        if tipo == 'whisper':
            pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
        else:
            pred_str = processor.batch_decode(pred_ids)

        label_str = processor.batch_decode(label_ids, skip_special_tokens=True)

        wer = wer_metric.compute(predictions=pred_str, references=label_str)
        cer = cer_metric.compute(predictions=pred_str, references=label_str)
        return {'wer': round(wer, 4), 'cer': round(cer, 4)}

    return compute_metrics


def _build_training_args(tipo: str, output_dir: str, config: Dict, fp16: bool):
    if tipo == 'whisper':
        from transformers import Seq2SeqTrainingArguments
        return Seq2SeqTrainingArguments(
            output_dir=output_dir,
            per_device_train_batch_size=config.get('per_device_train_batch_size', 4),
            per_device_eval_batch_size=config.get('per_device_eval_batch_size', 4),
            gradient_accumulation_steps=config.get('gradient_accumulation_steps', 2),
            learning_rate=config.get('learning_rate', 1e-5),
            warmup_steps=config.get('warmup_steps', 100),
            num_train_epochs=config.get('num_train_epochs', 20),
            weight_decay=config.get('weight_decay', 0.01),
            fp16=fp16,
            evaluation_strategy='epoch',
            save_strategy='epoch',
            load_best_model_at_end=True,
            metric_for_best_model='wer',
            greater_is_better=False,
            logging_steps=10,
            predict_with_generate=True,
            generation_max_length=225,
            push_to_hub=False,
            report_to=[],
        )
    else:
        from transformers import TrainingArguments
        return TrainingArguments(
            output_dir=output_dir,
            group_by_length=True,
            per_device_train_batch_size=config.get('per_device_train_batch_size', 4),
            per_device_eval_batch_size=config.get('per_device_eval_batch_size', 4),
            gradient_accumulation_steps=config.get('gradient_accumulation_steps', 2),
            evaluation_strategy='epoch',
            num_train_epochs=config.get('num_train_epochs', 20),
            fp16=fp16,
            gradient_checkpointing=True,
            learning_rate=config.get('learning_rate', 1e-4),
            weight_decay=config.get('weight_decay', 0.005),
            warmup_steps=config.get('warmup_steps', 100),
            save_strategy='epoch',
            load_best_model_at_end=True,
            metric_for_best_model='wer',
            greater_is_better=False,
            logging_steps=10,
            push_to_hub=False,
            report_to=[],
        )


def _get_trainer_class(tipo: str):
    if tipo == 'whisper':
        from transformers import Seq2SeqTrainer
        return Seq2SeqTrainer, {}
    from transformers import Trainer
    return Trainer, {}


def _apply_peft(model, tipo: str, config: Dict):
    """Aplica LoRA al modelo si use_peft=True."""
    try:
        from peft import LoraConfig, get_peft_model, TaskType
    except ImportError:
        logger.warning('peft no instalado, se omite LoRA. Instala con: pip install peft')
        return model

    if tipo == 'whisper':
        task_type = TaskType.SEQ_2_SEQ_LM
        target_modules = ['q_proj', 'v_proj']
    else:
        task_type = TaskType.SEQ_2_SEQ_LM
        target_modules = ['k_proj', 'v_proj', 'q_proj', 'out_proj']

    lora_config = LoraConfig(
        r=config.get('peft_r', 16),
        lora_alpha=config.get('peft_alpha', 32),
        target_modules=target_modules,
        lora_dropout=config.get('peft_dropout', 0.05),
        bias='none',
        task_type=task_type,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


class _MLflowEpochCallback:
    """Callback que registra métricas de evaluación en MLflow después de cada época."""

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        try:
            import mlflow
            if metrics:
                mlflow.log_metrics(
                    {k: v for k, v in metrics.items() if isinstance(v, (int, float))},
                    step=int(state.global_step),
                )
        except Exception as exc:
            logger.debug('MLflow log error: %s', exc)
