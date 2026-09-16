import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0005_perfilusuario_rol_fk_populate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='perfilusuario',
            name='rol',
        ),
        migrations.RenameField(
            model_name='perfilusuario',
            old_name='rol_fk',
            new_name='rol',
        ),
        migrations.AlterField(
            model_name='perfilusuario',
            name='rol',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='perfiles',
                to='roles.rol',
            ),
        ),
    ]
