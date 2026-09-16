# Generated manually for dynamic module/submodule administration.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0002_seed_catalogo'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='permiso',
            unique_together=set(),
        ),
        migrations.CreateModel(
            name='SubModulo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.SlugField(max_length=50)),
                ('nombre', models.CharField(max_length=100)),
                ('descripcion', models.TextField(blank=True)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('modulo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submodulos', to='roles.modulo')),
            ],
            options={
                'verbose_name': 'Submódulo',
                'verbose_name_plural': 'Submódulos',
                'db_table': 'roles_submodulos',
                'ordering': ['modulo__orden', 'orden', 'nombre'],
            },
        ),
        migrations.AddField(
            model_name='permiso',
            name='activo',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name='permiso',
            name='submodulo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='permisos', to='roles.submodulo'),
        ),
        migrations.AlterUniqueTogether(
            name='submodulo',
            unique_together={('modulo', 'codigo')},
        ),
        migrations.AlterUniqueTogether(
            name='permiso',
            unique_together={('modulo', 'submodulo', 'codigo')},
        ),
        migrations.AlterModelOptions(
            name='permiso',
            options={
                'ordering': ['modulo__orden', 'submodulo__orden', 'codigo'],
                'verbose_name': 'Permiso',
                'verbose_name_plural': 'Permisos',
            },
        ),
    ]
