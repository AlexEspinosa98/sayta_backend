import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traduccion', '0001_initial'),
        ('terminos', '__latest__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialTermino',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('termino_id_original', models.IntegerField(blank=True, db_index=True, null=True)),
                ('termino_texto', models.CharField(blank=True, max_length=255)),
                ('lengua_codigo', models.CharField(blank=True, db_index=True, max_length=20)),
                ('accion', models.CharField(choices=[('crear', 'Creó'), ('editar', 'Editó'), ('eliminar', 'Eliminó'), ('restaurar', 'Restauró'), ('desactivar', 'Desactivó')], db_index=True, max_length=12)),
                ('cambios', models.JSONField(default=dict)),
                ('usuario_nombre', models.CharField(blank=True, max_length=150)),
                ('origen', models.CharField(blank=True, max_length=30)),
                ('creado_en', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('termino', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='historial', to='terminos.terminoleng')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cambios_glosario', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Historial de término', 'verbose_name_plural': 'Historial de términos', 'db_table': 'traduccion_historial_terminos', 'ordering': ['-creado_en', '-id']},
        ),
    ]
