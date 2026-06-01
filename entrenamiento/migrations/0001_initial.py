import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('terminos', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModeloAudio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_hf', models.CharField(db_index=True, max_length=255, unique=True)),
                ('tipo', models.CharField(
                    choices=[('wav2vec2', 'Wav2Vec2 (CTC)'), ('whisper', 'Whisper (Seq2Seq)')],
                    max_length=20,
                )),
                ('descripcion', models.TextField(blank=True)),
                ('ruta_local', models.CharField(blank=True, max_length=500)),
                ('descargado', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Modelo de Audio',
                'verbose_name_plural': 'Modelos de Audio',
                'db_table': 'modelos_audio',
                'ordering': ['nombre_hf'],
            },
        ),
        migrations.CreateModel(
            name='ExperimentoEntrenamiento',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nombre', models.CharField(max_length=255)),
                ('comunidades_usadas', models.JSONField(default=list)),
                ('estado', models.CharField(
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('entrenando', 'Entrenando'),
                        ('completado', 'Completado'),
                        ('activo', 'Activo'),
                        ('fallido', 'Fallido'),
                    ],
                    db_index=True,
                    default='pendiente',
                    max_length=20,
                )),
                ('is_active', models.BooleanField(db_index=True, default=False)),
                ('config_entrenamiento', models.JSONField(default=dict)),
                ('ruta_modelo_entrenado', models.CharField(blank=True, max_length=500)),
                ('mlflow_run_id', models.CharField(blank=True, max_length=255)),
                ('mlflow_experiment_id', models.CharField(blank=True, max_length=255)),
                ('mlflow_experiment_name', models.CharField(blank=True, max_length=255)),
                ('mlflow_tracking_uri', models.CharField(blank=True, max_length=500)),
                ('metricas', models.JSONField(default=dict)),
                ('num_muestras_train', models.IntegerField(default=0)),
                ('num_muestras_eval', models.IntegerField(default=0)),
                ('error_mensaje', models.TextField(blank=True)),
                ('task_id', models.CharField(blank=True, db_index=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('lengua', models.ForeignKey(
                    db_index=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='experimentos_audio',
                    to='terminos.lengua',
                )),
                ('modelo_base', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='experimentos',
                    to='entrenamiento.modeloaudio',
                )),
            ],
            options={
                'verbose_name': 'Experimento de Entrenamiento',
                'verbose_name_plural': 'Experimentos de Entrenamiento',
                'db_table': 'experimentos_entrenamiento',
                'ordering': ['-created_at'],
            },
        ),
    ]
