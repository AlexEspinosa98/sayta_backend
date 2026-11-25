import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenamiento', '0003_experimento_reentrenado_de'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrabajoEntrenamiento',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('samples', models.JSONField(default=list)),
                ('config', models.JSONField(default=dict)),
                ('estado', models.CharField(choices=[('en_cola', 'En cola'), ('ejecutando', 'Ejecutando'), ('cancelar', 'Cancelando'), ('terminado', 'Terminado'), ('cancelado', 'Cancelado'), ('fallido', 'Fallido')], db_index=True, default='en_cola', max_length=20)),
                ('worker', models.CharField(blank=True, max_length=100)),
                ('mensaje', models.TextField(blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('iniciado_en', models.DateTimeField(blank=True, null=True)),
                ('terminado_en', models.DateTimeField(blank=True, null=True)),
                ('experimento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trabajos', to='entrenamiento.experimentoentrenamiento')),
            ],
            options={'verbose_name': 'Trabajo de entrenamiento', 'verbose_name_plural': 'Trabajos de entrenamiento', 'db_table': 'entrenamiento_trabajos', 'ordering': ['creado_en']},
        ),
    ]
