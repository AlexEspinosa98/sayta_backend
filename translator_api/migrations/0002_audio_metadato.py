import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('translator_api', '0001_etiqueta_historial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AudioMetadato',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comunidad', models.CharField(db_index=True, max_length=100)),
                ('jornada', models.CharField(db_index=True, max_length=200)),
                ('audio', models.CharField(max_length=255)),
                ('hablante', models.CharField(blank=True, db_index=True, max_length=120)),
                ('sexo', models.CharField(blank=True, max_length=20)),
                ('edad_aprox', models.CharField(blank=True, max_length=30)),
                ('notas', models.TextField(blank=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='metadatos_audio', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Metadato de audio', 'verbose_name_plural': 'Metadatos de audio', 'db_table': 'audio_metadatos', 'unique_together': {('comunidad', 'jornada', 'audio')}},
        ),
    ]
