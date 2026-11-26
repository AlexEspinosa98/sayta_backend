import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('traduccion', '0002_historial_termino'),
        ('terminos', '__latest__'),
    ]

    operations = [
        migrations.CreateModel(
            name='TerminoFaltante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('direccion', models.CharField(default='es_a_lengua', max_length=20)),
                ('texto', models.CharField(max_length=200)),
                ('texto_normalizado', models.CharField(db_index=True, max_length=200)),
                ('ejemplo_frase', models.TextField(blank=True)),
                ('veces', models.IntegerField(default=1)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('resuelto', 'Resuelto'), ('descartado', 'Descartado')], db_index=True, default='pendiente', max_length=12)),
                ('nota', models.TextField(blank=True)),
                ('primera_vez', models.DateTimeField(auto_now_add=True)),
                ('ultima_vez', models.DateTimeField(auto_now=True, db_index=True)),
                ('lengua', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='terminos_faltantes', to='terminos.lengua')),
                ('termino', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='faltantes_resueltos', to='terminos.terminoleng')),
            ],
            options={
                'verbose_name': 'Término faltante',
                'verbose_name_plural': 'Términos faltantes',
                'db_table': 'traduccion_terminos_faltantes',
                'ordering': ['-veces', '-ultima_vez'],
                'unique_together': {('lengua', 'direccion', 'texto_normalizado')},
            },
        ),
    ]
