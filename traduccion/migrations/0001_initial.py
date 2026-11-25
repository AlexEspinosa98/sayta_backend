import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('terminos', '__latest__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsultaTraduccion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('direccion', models.CharField(max_length=20)),
                ('origen', models.CharField(default='texto', max_length=20)),
                ('texto', models.TextField()),
                ('texto_normalizado', models.CharField(blank=True, db_index=True, max_length=500)),
                ('mejor_termino', models.CharField(blank=True, max_length=500)),
                ('mejor_termino_es', models.CharField(blank=True, max_length=500)),
                ('confianza', models.IntegerField(blank=True, null=True)),
                ('nivel', models.CharField(blank=True, max_length=20)),
                ('fuente', models.CharField(blank=True, max_length=20)),
                ('en_glosario', models.BooleanField(db_index=True, default=False)),
                ('verificacion_estado', models.CharField(blank=True, max_length=30)),
                ('verificacion_ms', models.IntegerField(blank=True, null=True)),
                ('ms_total', models.IntegerField(blank=True, null=True)),
                ('eleccion_usuario', models.IntegerField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('lengua', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consultas_traduccion', to='terminos.lengua')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consultas_traduccion', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Consulta de traducción', 'verbose_name_plural': 'Consultas de traducción', 'db_table': 'traduccion_consultas', 'ordering': ['-creado_en']},
        ),
        migrations.CreateModel(
            name='CorreccionTraduccion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[('correccion', 'Corrección'), ('validacion_hipotesis', 'Validación de hipótesis'), ('validacion_compuesta', 'Validación de traducción compuesta')], db_index=True, default='correccion', max_length=30)),
                ('direccion', models.CharField(blank=True, max_length=20)),
                ('texto_origen', models.TextField(blank=True)),
                ('propuesta_sistema', models.TextField(blank=True)),
                ('correccion', models.TextField(blank=True)),
                ('es_correcta', models.BooleanField(blank=True, null=True)),
                ('comentario', models.TextField(blank=True)),
                ('veredicto', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('rechazada', 'Rechazada')], db_index=True, default='pendiente', max_length=20)),
                ('aplicada', models.BooleanField(default=False)),
                ('usuario_nombre', models.CharField(blank=True, max_length=150)),
                ('revisado_en', models.DateTimeField(blank=True, null=True)),
                ('nota_revision', models.TextField(blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('consulta', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='correcciones', to='traduccion.consultatraduccion')),
                ('lengua', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correcciones_traduccion', to='terminos.lengua')),
                ('termino', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='correcciones', to='terminos.terminoleng')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='correcciones_traduccion', to=settings.AUTH_USER_MODEL)),
                ('revisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='correcciones_revisadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Corrección de traducción', 'verbose_name_plural': 'Correcciones de traducción', 'db_table': 'traduccion_correcciones', 'ordering': ['-creado_en']},
        ),
    ]
