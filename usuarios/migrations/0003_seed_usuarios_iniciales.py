"""
Data migration: crea los usuarios iniciales del sistema.

  - investigador_sayta  / rol: investigador
  - dev_sayta           / rol: desarrollador

Las contraseñas se hashean en tiempo de migración con el hasher por defecto
de Django (PBKDF2-SHA256). Cámbialas con:
  python manage.py changepassword investigador_sayta
  python manage.py changepassword dev_sayta
"""

from django.contrib.auth.hashers import make_password
from django.db import migrations


USUARIOS_SEMILLA = [
    {
        'username': 'investigador_sayta',
        'email': 'investigador@sayta.co',
        'first_name': 'Investigador',
        'last_name': 'Sayta',
        'password_plain': 'Investigador2026!',
        'rol': 'investigador',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'dev_sayta',
        'email': 'dev@sayta.co',
        'first_name': 'Desarrollador',
        'last_name': 'Sayta',
        'password_plain': 'Developer2026!',
        'rol': 'desarrollador',
        'is_staff': True,
        'is_superuser': False,
    },
]


def crear_usuarios(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    PerfilUsuario = apps.get_model('usuarios', 'PerfilUsuario')

    for data in USUARIOS_SEMILLA:
        rol = data['rol']
        password_hash = make_password(data['password_plain'])

        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'email': data['email'],
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'password': password_hash,
                'is_active': True,
                'is_staff': data['is_staff'],
                'is_superuser': data['is_superuser'],
            },
        )

        if not created:
            # El usuario ya existía — solo aseguramos que tenga perfil correcto
            pass

        PerfilUsuario.objects.get_or_create(
            usuario=user,
            defaults={'rol': rol},
        )


def eliminar_usuarios(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    usernames = [d['username'] for d in USUARIOS_SEMILLA]
    User.objects.filter(username__in=usernames).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_add_desarrollador_role'),
    ]

    operations = [
        migrations.RunPython(crear_usuarios, eliminar_usuarios),
    ]
