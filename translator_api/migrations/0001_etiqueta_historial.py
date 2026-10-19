import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EtiquetaHistorial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comunidad', models.CharField(db_index=True, max_length=100)),
                ('jornada', models.CharField(db_index=True, max_length=200)),
                ('audio', models.CharField(max_length=255)),
                ('accion', models.CharField(choices=[('crear', 'Creó'), ('editar', 'Editó'), ('eliminar', 'Eliminó')], max_length=10)),
                ('etiqueta_anterior', models.TextField(blank=True, default='')),
                ('etiqueta_nueva', models.TextField(blank=True, default='')),
                ('usuario_nombre', models.CharField(blank=True, default='', max_length=150)),
                ('origen', models.CharField(choices=[('app', 'Registrado al guardar'), ('auditoria', 'Reconstruido desde la auditoría')], default='app', max_length=10)),
                ('aproximado', models.BooleanField(default=False)),
                ('creado_en', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='etiquetas_historial', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Historial de etiqueta',
                'verbose_name_plural': 'Historial de etiquetas',
                'db_table': 'etiquetas_historial',
                'ordering': ['-creado_en', '-id'],
                'indexes': [models.Index(fields=['comunidad', 'jornada', 'audio'], name='etiquetas_h_comunid_392acb_idx')],
            },
        ),
    ]
