"""
Servicio de fine-tuning de modelos ASR (Wav2Vec2 / Whisper).

Flujo completo:
  1. Cargar muestras etiquetadas (audio + transcripción)
  2. Construir HuggingFace Dataset con split train/eval (90/10)
     — o K-Fold cross-validation si use_cv=True
  3. Preprocesar: resamplear a 16kHz, extraer features
  4. Wav2Vec2: construir vocabulario CTC desde los textos de entrenamiento
  5. Fine-tune con Trainer / Seq2SeqTrainer
  6. Loggear métricas por época en MLflow (WER, CER, loss)
  7. Guardar el mejor modelo en disco
  8. Actualizar ExperimentoEntrenamiento en BD

Config admitida (todos opcionales, con valores por defecto):
  num_train_epochs              int   = 20
  per_device_train_batch_size   int   = 4
  per_device_eval_batch_size    int   = 4
  gradient_accumulation_steps   int   = 2
  learning_rate                 float = 1e-4
  weight_decay                  float = 0.005
  warmup_steps                  int   = 100
  fp16                          bool  = auto (True si hay CUDA)
  use_peft                      bool  = False
  peft_r                        int   = 16
  peft_alpha                    int   = 32
  peft_dropout                  float = 0.05
  whisper_language              str   = 'es'
  whisper_task                  str   = 'transcribe'
  use_cv                        bool  = False   ← K-Fold cross-validation
  cv_folds                      int   = 5       ← número de folds
  mlflow_tracking_uri           str   = settings.MLFLOW_TRACKING_URI
"""

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
        exp.save(update_fields=[
            'estado', 'metricas', 'ruta_modelo_entrenado',
            'mlflow_run_id', 'mlflow_experiment_id', 'mlflow_experiment_name',
            'mlflow_tracking_uri', 'completed_at', 'error_mensaje',
        ])
        with _tasks_lock:
            _active_tasks.pop(task_id, None)

    except Exception as exc:
        logger.exception('Entrenamiento %s falló: %s', experimento_id, exc)
        if exp is not None:
            try:
                from entrenamiento.models import ExperimentoEntrenamiento as _EE
                from django.utils import timezone as _tz
                exp.refresh_from_db()
                exp.estado = _EE.ESTADO_FALLIDO
                exp.error_mensaje = str(exc)
                exp.completed_at = _tz.now()
                exp.save(update_fields=['estado', 'error_mensaje', 'completed_at'])
            except Exception:
                pass
        with _tasks_lock:
            _active_tasks.pop(task_id, None)
    finally:
        connection.close()


# ==================================================================
# Núcleo del entrenamiento
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
        getattr(settings, 'MLFLOW_TRACKING_URI', f'sqlite:///{Path(settings.BASE_DIR) / "mlflow.db"}'),
    )
    mlflow.set_tracking_uri(tracking_uri)
    experiment_name = f'sayta-asr-{exp.lengua.codigo}'
    mlflow.set_experiment(experiment_name)

    # --- Serializar selección de datos para MLflow ---
    comunidades_info = exp.comunidades_usadas
    if isinstance(comunidades_info, dict):
        modo = comunidades_info.get('modo', 'desconocido')
        if modo == 'todos':
            comunidades_str = 'todos'
        elif modo == 'sesiones':
            partes = [f"{s['comunidad']}/{s['jornada']}" for s in comunidades_info.get('sesiones', [])]
            comunidades_str = ', '.join(partes[:5])  # MLflow limita longitud de params
            if len(partes) > 5:
                comunidades_str += f' (+{len(partes) - 5} más)'
        else:
            comunidades_str = ', '.join(comunidades_info.get('comunidades', []))
    else:
        comunidades_str = str(comunidades_info)

    use_cv = config.get('use_cv', False)
    cv_folds = int(config.get('cv_folds', 5))
    use_fp16 = config.get('fp16', torch.cuda.is_available())

    with mlflow.start_run(run_name=exp.nombre) as run:
        run_id = run.info.run_id
        exp_mlflow_id = run.info.experiment_id

        # --- Log hiperparámetros base ---
        mlflow.log_params({
            'modelo_base': modelo_hf,
            'tipo_modelo': tipo,
            'lengua': exp.lengua.codigo,
            'seleccion': comunidades_str,
            'num_muestras_total': len(samples),
            'epochs': config.get('num_train_epochs', 20),
            'learning_rate': config.get('learning_rate', 1e-4),
            'batch_size': config.get('per_device_train_batch_size', 4),
            'gradient_accumulation': config.get('gradient_accumulation_steps', 2),
            'warmup_steps': config.get('warmup_steps', 100),
            'weight_decay': config.get('weight_decay', 0.005),
            'use_peft': config.get('use_peft', False),
            'use_cv': use_cv,
            'cv_folds': cv_folds if use_cv else 1,
            'fp16': use_fp16,
        })

        output_dir = str(
            Path(getattr(settings, 'MODELOS_ENTRENADOS_DIR', str(Path(settings.BASE_DIR) / 'modelos_entrenados')))
            / str(exp.id)
        )
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if use_cv:
            metricas, output_dir = _run_cross_validation(
                exp, samples, config, tipo, modelo_hf, ruta_local,
                output_dir, use_fp16, cv_folds, mlflow,
            )
        else:
            metricas, output_dir = _run_single_split(
                exp, samples, config, tipo, modelo_hf, ruta_local,
                output_dir, use_fp16, mlflow,
            )

        # --- Guardar config como artefacto ---
        config_path = Path(output_dir) / 'training_config.json'
        config_path.write_text(json.dumps(config, indent=2, default=str), encoding='utf-8')
        mlflow.log_artifact(str(config_path))

        mlflow.log_metrics({k: v for k, v in metricas.items() if isinstance(v, (int, float))})
        logger.info('Métricas finales: %s', metricas)

    return metricas, output_dir, run_id, exp_mlflow_id, experiment_name, tracking_uri


# ==================================================================
# Estrategia 1 — Split simple 90/10
# ==================================================================

def _run_single_split(exp, samples, config, tipo, modelo_hf, ruta_local,
                      output_dir, use_fp16, mlflow):
    model, processor = _load_model_for_training(tipo, modelo_hf, ruta_local, samples, config)
    train_ds, eval_ds = _build_hf_dataset(samples, processor, tipo)

    exp.num_muestras_train = len(train_ds)
    exp.num_muestras_eval = len(eval_ds)
    exp.save(update_fields=['num_muestras_train', 'num_muestras_eval'])

    mlflow.log_params({'num_train': len(train_ds), 'num_eval': len(eval_ds)})

    if config.get('use_peft', False):
        model = _apply_peft(model, tipo, config)

    training_args = _build_training_args(tipo, output_dir, config, use_fp16)
    data_collator = _build_collator(tipo, processor, model)
    compute_metrics_fn = _build_compute_metrics(processor, tipo)

    TrainerClass, extra_kwargs = _get_trainer_class(tipo)
    trainer = TrainerClass(
        model=model,
        args=training_args,
        compute_metrics=compute_metrics_fn,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        callbacks=[_MLflowEpochCallback()],
        **extra_kwargs,
    )

    logger.info('Entrenamiento simple: %d train / %d eval', len(train_ds), len(eval_ds))
    train_result = trainer.train()
    trainer.save_model(output_dir)
    if hasattr(processor, 'save_pretrained'):
        processor.save_pretrained(output_dir)

    eval_results = trainer.evaluate()

    return {
        'train_loss': round(train_result.training_loss, 4),
        'eval_loss': round(eval_results.get('eval_loss', 0.0), 4),
        'eval_wer': round(eval_results.get('eval_wer', 1.0), 4),
        'eval_cer': round(eval_results.get('eval_cer', 1.0), 4),
        'total_steps': train_result.global_step,
        'epochs': training_args.num_train_epochs,
        'runtime_segundos': round(eval_results.get('eval_runtime', 0.0), 1),
        'estrategia': 'split_simple',
    }, output_dir


# ==================================================================
# Estrategia 2 — K-Fold Cross-Validation
# ==================================================================

def _run_cross_validation(exp, samples, config, tipo, modelo_hf, ruta_local,
                          output_dir, use_fp16, k, mlflow):
    """
    K-Fold CV: entrena K modelos, reporta métricas medias ± std.
    Guarda el mejor fold (menor WER) como modelo final.
    """
    from sklearn.model_selection import KFold
    import numpy as np

    kf = KFold(n_splits=k, shuffle=True, random_state=42)
    indices = list(range(len(samples)))

    fold_metrics: List[Dict] = []
    best_wer = float('inf')
    best_fold_dir = output_dir

    logger.info('Iniciando %d-Fold Cross-Validation con %d muestras', k, len(samples))

    total_train = 0
    total_eval = 0

    for fold_idx, (train_idx, eval_idx) in enumerate(kf.split(indices), start=1):
        fold_samples_train = [samples[i] for i in train_idx]
        fold_samples_eval = [samples[i] for i in eval_idx]
        fold_dir = str(Path(output_dir) / f'fold_{fold_idx}')
        Path(fold_dir).mkdir(parents=True, exist_ok=True)

        logger.info('Fold %d/%d — train: %d, eval: %d', fold_idx, k,
                    len(fold_samples_train), len(fold_samples_eval))

        mlflow.log_params({
            f'fold_{fold_idx}_train': len(fold_samples_train),
            f'fold_{fold_idx}_eval': len(fold_samples_eval),
        })

        # Cargar modelo fresco para cada fold
        model, processor = _load_model_for_training(
            tipo, modelo_hf, ruta_local, fold_samples_train, config
        )
        if config.get('use_peft', False):
            model = _apply_peft(model, tipo, config)

        train_ds, _ = _build_hf_dataset(fold_samples_train, processor, tipo)
        _, eval_ds = _build_hf_dataset(fold_samples_eval, processor, tipo)

        total_train += len(train_ds)
        total_eval += len(eval_ds)

        training_args = _build_training_args(tipo, fold_dir, config, use_fp16)
        data_collator = _build_collator(tipo, processor, model)
        compute_metrics_fn = _build_compute_metrics(processor, tipo)

        TrainerClass, extra_kwargs = _get_trainer_class(tipo)
        trainer = TrainerClass(
            model=model,
            args=training_args,
            compute_metrics=compute_metrics_fn,
            train_dataset=train_ds,
            eval_dataset=eval_ds,
            data_collator=data_collator,
            callbacks=[_MLflowEpochCallback(fold=fold_idx)],
            **extra_kwargs,
        )

        train_result = trainer.train()
        trainer.save_model(fold_dir)
        if hasattr(processor, 'save_pretrained'):
            processor.save_pretrained(fold_dir)

        eval_results = trainer.evaluate()
        fold_wer = eval_results.get('eval_wer', 1.0)
        fold_cer = eval_results.get('eval_cer', 1.0)

        fold_m = {
            'fold': fold_idx,
            'train_loss': round(train_result.training_loss, 4),
            'eval_loss': round(eval_results.get('eval_loss', 0.0), 4),
            'eval_wer': round(fold_wer, 4),
            'eval_cer': round(fold_cer, 4),
            'steps': train_result.global_step,
        }
        fold_metrics.append(fold_m)

        mlflow.log_metrics({
            f'fold_{fold_idx}_wer': fold_wer,
            f'fold_{fold_idx}_cer': fold_cer,
            f'fold_{fold_idx}_train_loss': train_result.training_loss,
        }, step=fold_idx)

        logger.info('Fold %d — WER: %.4f  CER: %.4f  loss: %.4f',
                    fold_idx, fold_wer, fold_cer, train_result.training_loss)

        if fold_wer < best_wer:
            best_wer = fold_wer
            best_fold_dir = fold_dir

    # --- Métricas agregadas ---
    wers = [m['eval_wer'] for m in fold_metrics]
    cers = [m['eval_cer'] for m in fold_metrics]
    losses = [m['train_loss'] for m in fold_metrics]
    eval_losses = [m['eval_loss'] for m in fold_metrics]

    mean_wer = float(np.mean(wers))
    std_wer = float(np.std(wers))
    mean_cer = float(np.mean(cers))
    std_cer = float(np.std(cers))

    mlflow.log_metrics({
        'cv_mean_wer': mean_wer,
        'cv_std_wer': std_wer,
        'cv_mean_cer': mean_cer,
        'cv_std_cer': std_cer,
        'cv_best_wer': best_wer,
    })

    # Actualizar contadores en BD con los del mejor fold
    exp.num_muestras_train = total_train // k
    exp.num_muestras_eval = total_eval // k
    exp.save(update_fields=['num_muestras_train', 'num_muestras_eval'])

    # --- Copiar mejor fold como modelo final ---
    import shutil
    if best_fold_dir != output_dir:
        for f in Path(best_fold_dir).iterdir():
            dest = Path(output_dir) / f.name
            if not dest.exists():
                shutil.copy2(str(f), str(dest))

    # Guardar resumen de folds como artefacto
    cv_summary_path = Path(output_dir) / 'cv_summary.json'
    cv_summary_path.write_text(
        json.dumps({
            'k': k,
            'folds': fold_metrics,
            'mean_wer': round(mean_wer, 4),
            'std_wer': round(std_wer, 4),
            'mean_cer': round(mean_cer, 4),
            'std_cer': round(std_cer, 4),
            'best_fold': min(fold_metrics, key=lambda x: x['eval_wer'])['fold'],
            'best_wer': round(best_wer, 4),
        }, indent=2),
        encoding='utf-8',
    )
    mlflow.log_artifact(str(cv_summary_path))

    metricas = {
        'train_loss': round(float(np.mean(losses)), 4),
        'eval_loss': round(float(np.mean(eval_losses)), 4),
        'eval_wer': round(mean_wer, 4),
        'eval_wer_std': round(std_wer, 4),
        'eval_cer': round(mean_cer, 4),
        'eval_cer_std': round(std_cer, 4),
        'best_fold_wer': round(best_wer, 4),
        'total_steps': sum(m['steps'] for m in fold_metrics),
        'epochs': config.get('num_train_epochs', 20),
        'estrategia': f'cross_validation_{k}_folds',
    }

    logger.info(
        'CV completo — WER: %.4f ± %.4f  CER: %.4f ± %.4f  mejor fold WER: %.4f',
        mean_wer, std_wer, mean_cer, std_cer, best_wer,
    )
    return metricas, output_dir


# ==================================================================
# Helpers de entrenamiento
# ==================================================================

def _check_deps():
    missing = []
    for pkg in ('transformers', 'datasets', 'evaluate', 'mlflow',
                'librosa', 'soundfile', 'jiwer', 'sklearn'):
        try:
            __import__(pkg if pkg != 'sklearn' else 'sklearn.model_selection')
        except ImportError:
            missing.append(pkg if pkg != 'sklearn' else 'scikit-learn')
    if missing:
        raise RuntimeError(
            f'Dependencias faltantes: {", ".join(missing)}. '
            f'Instala con: pip install {" ".join(missing)}'
        )


def _load_model_for_training(tipo: str, modelo_hf: str, ruta_local: str,
                              samples: List[Dict], config: Dict):
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

        # Construir vocabulario CTC desde los textos de entrenamiento
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
        # freeze_feature_encoder reemplaza al deprecado freeze_feature_extractor
        if hasattr(model, 'freeze_feature_encoder'):
            model.freeze_feature_encoder()
        elif hasattr(model, 'freeze_feature_extractor'):
            model.freeze_feature_extractor()
        return model, processor


def _load_audio_16k(audio_path: str):
    """Carga y resamplea audio a 16kHz. Retorna numpy array."""
    import librosa
    speech, _ = librosa.load(audio_path, sr=16000, mono=True)
    return speech


def _build_hf_dataset(samples: List[Dict], processor, tipo: str):
    """Construye HF Dataset preprocesado y hace split 90/10."""
    import datasets as hf_datasets

    raw_data: Dict[str, List] = {'audio': [], 'sentence': []}
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

    if tipo == 'whisper':
        def preprocess_whisper(batch):
            features = processor(
                batch['audio'], sampling_rate=16000, return_tensors='np'
            ).input_features[0]
            # processor.tokenizer directamente (as_target_processor deprecado en ≥4.44)
            labels = processor.tokenizer(batch['sentence']).input_ids
            return {'input_features': features, 'labels': labels}

        train_ds = split['train'].map(preprocess_whisper, remove_columns=['audio', 'sentence'])
        eval_ds = split['test'].map(preprocess_whisper, remove_columns=['audio', 'sentence'])

    else:  # wav2vec2
        def preprocess_wav2vec2(batch):
            inputs = processor(batch['audio'], sampling_rate=16000)
            # processor.tokenizer directamente (as_target_processor deprecado en ≥4.44)
            labels = processor.tokenizer(batch['sentence'])
            return {
                'input_values': inputs.input_values[0],
                'labels': labels.input_ids,
            }

        train_ds = split['train'].map(preprocess_wav2vec2, remove_columns=['audio', 'sentence'])
        eval_ds = split['test'].map(preprocess_wav2vec2, remove_columns=['audio', 'sentence'])

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
        # tokenizer.pad directamente (as_target_processor deprecado en ≥4.44)
        labels_batch = self.processor.tokenizer.pad(
            label_features, padding=self.padding, return_tensors='pt'
        )
        labels = labels_batch['input_ids'].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )
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
        labels = labels_batch['input_ids'].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )
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
        pred_ids = (
            np.argmax(pred.predictions, axis=-1)
            if tipo == 'wav2vec2'
            else pred.predictions
        )
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

        pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.batch_decode(label_ids, skip_special_tokens=True)

        wer = wer_metric.compute(predictions=pred_str, references=label_str)
        cer = cer_metric.compute(predictions=pred_str, references=label_str)
        return {'wer': round(wer, 4), 'cer': round(cer, 4)}

    return compute_metrics


def _build_training_args(tipo: str, output_dir: str, config: Dict, fp16: bool):
    """
    Construye TrainingArguments compatible con transformers >= 4.46.
    evaluation_strategy fue renombrado a eval_strategy en 4.46.
    """
    import transformers

    # Detectar versión para compatibilidad
    tf_version = tuple(int(x) for x in transformers.__version__.split('.')[:2])
    use_eval_strategy = tf_version >= (4, 46)
    strategy_kwarg = 'eval_strategy' if use_eval_strategy else 'evaluation_strategy'

    common = {
        'output_dir': output_dir,
        'per_device_train_batch_size': config.get('per_device_train_batch_size', 4),
        'per_device_eval_batch_size': config.get('per_device_eval_batch_size', 4),
        'gradient_accumulation_steps': config.get('gradient_accumulation_steps', 2),
        'learning_rate': config.get('learning_rate', 1e-5 if tipo == 'whisper' else 1e-4),
        'warmup_steps': config.get('warmup_steps', 100),
        'num_train_epochs': config.get('num_train_epochs', 20),
        'weight_decay': config.get('weight_decay', 0.01),
        'fp16': fp16,
        strategy_kwarg: 'epoch',
        'save_strategy': 'epoch',
        'load_best_model_at_end': True,
        'metric_for_best_model': 'wer',
        'greater_is_better': False,
        'logging_steps': 10,
        'push_to_hub': False,
        'report_to': [],
    }

    if tipo == 'whisper':
        from transformers import Seq2SeqTrainingArguments
        return Seq2SeqTrainingArguments(
            predict_with_generate=True,
            generation_max_length=225,
            **common,
        )
    else:
        from transformers import TrainingArguments
        return TrainingArguments(
            group_by_length=True,
            gradient_checkpointing=True,
            **common,
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
        from peft import LoraConfig, TaskType, get_peft_model
    except ImportError:
        logger.warning('peft no instalado, se omite LoRA. Instala con: pip install peft')
        return model

    task_type = TaskType.SEQ_2_SEQ_LM
    target_modules = (
        ['q_proj', 'v_proj']
        if tipo == 'whisper'
        else ['k_proj', 'v_proj', 'q_proj', 'out_proj']
    )

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


# ==================================================================
# Callback MLflow — factory para heredar TrainerCallback correctamente
# ==================================================================

def _MLflowEpochCallback(fold: Optional[int] = None):
    """
    Factory que devuelve una instancia de TrainerCallback que loguea en MLflow.
    Se construye en tiempo de ejecución para evitar importar transformers a nivel
    de módulo (puede no estar instalado en todos los entornos).
    """
    from transformers import TrainerCallback

    class _Callback(TrainerCallback):
        _fold = fold

        def on_evaluate(self, args, state, control, metrics=None, **kwargs):
            try:
                import mlflow
                if not metrics:
                    return
                prefix = f'fold_{self._fold}_' if self._fold else ''
                mlflow.log_metrics(
                    {
                        f'{prefix}{k}': v
                        for k, v in metrics.items()
                        if isinstance(v, (int, float))
                    },
                    step=int(state.global_step),
                )
            except Exception as exc:
                logger.debug('MLflow log error: %s', exc)

    return _Callback()
