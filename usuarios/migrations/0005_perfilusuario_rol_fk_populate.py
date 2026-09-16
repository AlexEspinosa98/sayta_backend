"""Mapea el rol string existente (CharField) al nuevo Rol (FK) por código."""

from django.db import migrations


def poblar(apps, schema_editor):
    PerfilUsuario = apps.get_model('usuarios', 'PerfilUsuario')
    Rol = apps.get_model('roles', 'Rol')
    for perfil in PerfilUsuario.objects.all():
        rol = Rol.objects.filter(codigo=perfil.rol).first()
        if rol is None:
            continue
        perfil.rol_fk = rol
        perfil.save(update_fields=['rol_fk'])


def revertir(apps, schema_editor):
    PerfilUsuario = apps.get_model('usuarios', 'PerfilUsuario')
    PerfilUsuario.objects.update(rol_fk=None)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_perfilusuario_rol_fk_add'),
    ]

    operations = [
        migrations.RunPython(poblar, revertir),
    ]
