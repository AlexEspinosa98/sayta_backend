from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenamiento', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='experimentoentrenamiento',
            name='modelo_eliminado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='experimentoentrenamiento',
            name='bytes_liberados',
            field=models.BigIntegerField(default=0),
        ),
    ]
