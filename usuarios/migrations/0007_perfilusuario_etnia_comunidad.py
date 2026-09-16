# Generated manually for optional user community metadata.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_perfilusuario_rol_finalize'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='etnia',
            field=models.CharField(
                blank=True,
                choices=[('arhuaco', 'Arhuaco'), ('kogui', 'Kogui')],
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='comunidad',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
