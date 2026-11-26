from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('translator_api', '0002_audio_metadato'),
    ]

    operations = [
        migrations.AddField(
            model_name='audiometadato',
            name='traduccion_es',
            field=models.TextField(blank=True, default=''),
        ),
    ]
