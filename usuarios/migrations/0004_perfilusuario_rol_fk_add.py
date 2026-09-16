import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_seed_usuarios_iniciales'),
        ('roles', '0002_seed_catalogo'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='rol_fk',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='perfiles',
                to='roles.rol',
            ),
        ),
    ]
