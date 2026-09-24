# El rol 'pendiente' se añadió a 0002_seed_catalogo después de que esa
# migración ya se había aplicado en producción, así que nunca se creó y el
# auto-registro público fallaba con Rol.DoesNotExist. Esta migración lo
# garantiza en cualquier BD, exista o no.

from django.db import migrations


def crear_rol_pendiente(apps, schema_editor):
    Rol = apps.get_model('roles', 'Rol')
    Rol.objects.get_or_create(
        codigo='pendiente',
        defaults={
            'nombre': 'Pendiente de aprobación',
            'descripcion': (
                'Rol asignado automáticamente al auto-registrarse desde '
                'POST /api/auth/registro-publico/. No tiene ningún permiso — '
                'un administrador debe asignarle un rol real desde '
                'PATCH /api/auth/usuarios/<id>/ antes de que pueda usar el sistema.'
            ),
            'es_sistema': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0003_submodulos_permisos_activos'),
    ]

    operations = [
        # Reverse no-op: el rol puede tener usuarios asignados (FK PROTECT).
        migrations.RunPython(crear_rol_pendiente, migrations.RunPython.noop),
    ]
