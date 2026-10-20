import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entrenamiento', '0002_experimento_almacenamiento'),
    ]

    operations = [
        migrations.AddField(
            model_name='experimentoentrenamiento',
            name='reentrenado_de',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reentrenamientos', to='entrenamiento.experimentoentrenamiento'),
        ),
    ]
